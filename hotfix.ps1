Param(
  [string]$AppDir = (Get-Location).Path,
  [switch]$AddCourses = $true,     # add Courses feature so the Admin menu link works
  [switch]$TrimMenu   = $true,     # remove menu items to undefined endpoints (Import/Export, Calibration)
  [switch]$Backup     = $true      # create timestamped .bak files before changes
)

function Backup-File($path) {
  if (-not $Backup) { return }
  if (Test-Path $path) {
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $path "$path.$ts.bak" -Force
    Write-Host "Backed up $path -> $path.$ts.bak" -ForegroundColor Yellow
  }
}

function Get-FileText($path) {
  if (-not (Test-Path $path)) { throw "Missing file: $path" }
  return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
}

function Set-FileText($path, $text) {
  [System.IO.File]::WriteAllText($path, $text, [System.Text.Encoding]::UTF8)
}

function Replace-TopLevelFunction($content, $funcName, $newBlock) {
  # Find "def funcName(" start
  $start = $content.IndexOf("def $funcName(")
  if ($start -lt 0) {
    Write-Host "Function $funcName not found. Skipping replace." -ForegroundColor DarkYellow
    return $content
  }
  # Find the next top-level marker
  $rest = $content.Substring($start + 1)
  $regex = [regex]'(?m)^(def\s+|@app\.route|class\s+|#\s*----|\Z)'
  $m = $regex.Match($rest)
  $endIndex = if ($m.Success) { $start + 1 + $m.Index } else { $content.Length }
  $before = $content.Substring(0, $start)
  $after  = $content.Substring($endIndex)
  return ($before + $newBlock + "`r`n`r`n" + $after)
}

# --- Begin ---
Set-Location $AppDir
Write-Host "Patching in: $AppDir" -ForegroundColor Cyan

# 1) app.py
$appPath = Join-Path $AppDir "app.py"
$app = Get-FileText $appPath
Backup-File $appPath

# 1a) Safe Teams function (no f-strings)
$safeTeams = @'
def send_teams_card(title, text):
    if not TEAMS_WEBHOOK_URL:
        return False
    try:
        # No f-string to avoid accidental multi-line breaks
        payload = {"text": "**" + str(title) + "**\n\n" + str(text)}
        requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=5)
        return True
    except Exception:
        return False
'@
$app = Replace-TopLevelFunction $app "send_teams_card" $safeTeams

# 1b) Replace self_review() with robust version (triple-quoted .format emails)
$safeSelf = @'
@app.route('/review/self', methods=['GET','POST'])
@login_required
def self_review():
    user = current_user
    # Managers do not use self-review
    if getattr(user, 'is_manager', False):
        return redirect(url_for('manager_review'))

    exp_map = current_expectations_for(user)
    comp_ids = list(exp_map.keys())
    competencies = CompetencySkill.query.filter(CompetencySkill.id.in_(comp_ids)).all() if comp_ids else []
    cycles = ReviewCycle.query.order_by(ReviewCycle.start_date.desc().nullslast()).all()
    sel_cycle_id = request.values.get('cycle_id', type=int) or (current_cycle().id if current_cycle() else None)

    if request.method == 'POST':
        saved_any = False
        for c in competencies:
            val = request.form.get(f'comp_{c.id}')
            cmt = request.form.get(f'cmt_{c.id}', '').strip()
            if val is None:
                continue
            db.session.add(SelfEvaluation(
                user_id=user.id,
                competency_id=c.id,
                level=int(val),
                cycle_id=sel_cycle_id,
                comment=(cmt or None)
            ))
            saved_any = True

        if saved_any:
            db.session.commit()
            log_audit('UPSERT','SelfEvaluation', None, after={'user_id':user.id,'cycle_id':sel_cycle_id})

            # Email Manager (safe body)
            mgr = db.session.get(User, user.manager_id) if user.manager_id else None
            if mgr and mgr.email:
                emp_name = user.full_name or user.username
                mgr_name = mgr.full_name or mgr.username
                cycle_name = (db.session.get(ReviewCycle, sel_cycle_id).name if sel_cycle_id else 'Current')
                subj = "[PMS] Self Review submitted: " + emp_name
                body = """Hi {mgr_name},

{emp_name} has submitted a self review for cycle {cycle_name}.
Please log in to review: http://127.0.0.1:5000/review/manager

Regards,
PMS""".format(mgr_name=mgr_name, emp_name=emp_name, cycle_name=cycle_name)
                send_email(mgr.email, subj, body)

            flash('Self review saved and manager notified', 'success')
        return redirect(url_for('self_review', cycle_id=sel_cycle_id))

    self_map = latest_self_details(user.id)
    rows = []
    for c in competencies:
        expected, weight = exp_map.get(c.id, (0,1))
        self_level = self_map.get(c.id, {}).get('level', 0)
        self_comment = self_map.get(c.id, {}).get('comment', None)
        gap = max(expected - self_level, 0)
        weighted_gap = gap * (weight or 1)
        courses = recommend_courses(c.id, expected)
        rows.append({
            'competency': c,
            'expected': expected,
            'self_level': self_level,
            'gap': gap,
            'weighted_gap': weighted_gap,
            'courses': courses[:3],
            'self_comment': self_comment
        })

    return render_template('self_review.html', competencies=competencies, rows=rows, cycles=cycles, sel_cycle_id=sel_cycle_id)
'@
$app = Replace-TopLevelFunction $app "self_review" $safeSelf

# 1c) Replace manager_review() with robust version (triple-quoted .format emails)
$safeMgr = @'
@app.route('/review/manager', methods=['GET','POST'])
@login_required
def manager_review():
    if not getattr(current_user, 'is_manager', False):
        return redirect(url_for('index'))

    team = User.query.filter_by(manager_id=current_user.id).all()
    team_ids = {u.id for u in team}
    sel_user = None

    cycles = ReviewCycle.query.order_by(ReviewCycle.start_date.desc().nullslast()).all()
    sel_cycle_id = request.values.get('cycle_id', type=int) or (current_cycle().id if current_cycle() else None)

    if request.method == 'POST':
        user_id = int(request.form['user_id'])
        if user_id not in team_ids:
            flash('You can only review your direct reports.', 'danger')
            return redirect(url_for('manager_review'))

        sel_user = db.session.get(User, user_id)
        exp_map = current_expectations_for(sel_user)
        competencies = CompetencySkill.query.filter(CompetencySkill.id.in_(exp_map.keys())).all()

        saved_any = False
        for c in competencies:
            val = request.form.get(f'comp_{c.id}')
            cmt = request.form.get(f'cmt_{c.id}', '').strip()
            if val is None:
                continue
            db.session.add(ManagerEvaluation(
                user_id=sel_user.id,
                manager_id=current_user.id,
                competency_id=c.id,
                level=int(val),
                cycle_id=sel_cycle_id,
                comment=(cmt or None)
            ))
            saved_any = True

        if saved_any:
            db.session.commit()
            log_audit('UPSERT','ManagerEvaluation', None, after={'user_id':sel_user.id,'cycle_id':sel_cycle_id})

            if sel_user.email:
                mgr_name = current_user.full_name or current_user.username
                emp_name = sel_user.full_name or sel_user.username
                cycle_name = (db.session.get(ReviewCycle, sel_cycle_id).name if sel_cycle_id else 'Current')
                subj = "[PMS] Your Manager Review is updated: " + emp_name
                body = """Hi {emp_name},

Your manager ({mgr_name}) has submitted/updated your manager review for cycle {cycle_name}.
Please log in to view details.

Regards,
PMS""".format(emp_name=emp_name, mgr_name=mgr_name, cycle_name=cycle_name)
                send_email(sel_user.email, subj, body)

            flash('Manager review saved and employee notified', 'success')
        return redirect(url_for('manager_review', user_id=user_id, cycle_id=sel_cycle_id))

    user_id = request.args.get('user_id', type=int)
    if user_id:
        if user_id not in team_ids:
            flash('You can only view your direct reports.', 'danger')
            return redirect(url_for('manager_review'))
        sel_user = db.session.get(User, user_id)

    rows = []
    if sel_user:
        exp_map = current_expectations_for(sel_user)
        competencies = CompetencySkill.query.filter(CompetencySkill.id.in_(exp_map.keys())).all()
        self_map = latest_self_details(sel_user.id)
        man_lvls = {k:v[0] for k,v in latest_manager_levels(sel_user.id).items()}

        for c in competencies:
            expected, weight = exp_map.get(c.id, (0,1))
            actual = man_lvls.get(c.id, self_map.get(c.id, {}).get('level', 0))
            gap = max(expected - (actual or 0), 0)
            weighted_gap = gap * (weight or 1)
            courses = recommend_courses(c.id, expected)
            rows.append({
                'competency': c,
                'expected': expected,
                'self_level': self_map.get(c.id, {}).get('level'),
                'self_comment': self_map.get(c.id, {}).get('comment'),
                'manager_level': man_lvls.get(c.id, 0),
                'gap': gap,
                'weighted_gap': weighted_gap,
                'courses': courses[:3]
            })

    return render_template('manager_review.html', team=team, sel_user=sel_user, rows=rows, cycles=cycles, sel_cycle_id=sel_cycle_id)
'@
$app = Replace-TopLevelFunction $app "manager_review" $safeMgr

# 1d) Add Courses routes (if requested & missing)
if ($AddCourses) {
  if ($app -notmatch '(?m)^def\s+courses\s*\(') {
    Write-Host "Adding /admin/courses routes..." -ForegroundColor Green
    $coursesRoutes = @'
@app.route('/admin/courses', methods=['GET', 'POST'])
@login_required
@require_roles('ADMIN')
def courses():
    competencies = CompetencySkill.query.all()
    edit_id = request.args.get('edit_id', type=int)
    item = db.session.get(Course, edit_id) if edit_id else None

    if request.method == 'POST':
        title = request.form['title']
        competency_id = request.form.get('competency_id', type=int)
        min_level = int(request.form.get('min_level', 0))
        external_id = request.form.get('external_id')
        url = request.form.get('url')

        if item is None:
            item = Course(
                title=title, competency_id=competency_id, min_level=min_level,
                external_id=external_id, url=url
            )
            db.session.add(item)
        else:
            item.title = title
            item.competency_id = competency_id
            item.min_level = min_level
            item.external_id = external_id
            item.url = url
        db.session.commit()
        flash('Saved course', 'success')
        return redirect(url_for('courses'))

    rows = Course.query.order_by(Course.id).all()
    return render_template('courses.html', rows=rows, item=item, competencies=competencies)

@app.route('/admin/courses/delete/<int:id>')
@login_required
@require_roles('ADMIN')
def courses_delete(id):
    c = Course.query.get(id)
    if not c:
        flash('Course not found', 'danger')
        return redirect(url_for('courses'))
    db.session.delete(c)
    db.session.commit()
    flash('Deleted course', 'success')
    return redirect(url_for('courses'))
'@
    if ($app.Contains("# Flask 3 safe init")) {
      $app = $app -replace "(?s)# Flask 3 safe init", "$coursesRoutes`r`n# Flask 3 safe init"
    } else {
      $app = $app + "`r`n`r`n" + $coursesRoutes
    }
  } else {
    Write-Host "Courses routes already present. Skipping add." -ForegroundColor DarkYellow
  }
}

# Save app.py
Set-FileText $appPath $app
Write-Host "Patched app.py" -ForegroundColor Green

# 2) templates/base.html (trim broken links)
$basePath = Join-Path $AppDir "templates\base.html"
if (Test-Path $basePath) {
  Backup-File $basePath
  $base = Get-FileText $basePath

  if ($TrimMenu) {
    $hasCoursesRoute = ($app -match '(?m)^def\s+courses\s*\(')
    if (-not $hasCoursesRoute) {
      $base = [regex]::Replace($base, '(?m)^\s*<li>.*url_for\(''courses''\).*\r?\n', '', 'Singleline')
      Write-Host "Removed Courses menu (no courses route present)" -ForegroundColor Yellow
    }
    if ($app -notmatch "(?m)^def\s+import_export\s*\(") {
      $base = [regex]::Replace($base, '(?m)^\s*<li>.*url_for\(''import_export''\).*\r?\n', '', 'Singleline')
    }
    if ($app -notmatch "(?m)^def\s+calibration\s*\(") {
      $base = [regex]::Replace($base, '(?m)^\s*<li>.*url_for\(''calibration''\).*\r?\n', '', 'Singleline')
    }
  }

  Set-FileText $basePath $base
  Write-Host "Patched templates/base.html" -ForegroundColor Green
} else {
  Write-Host "templates/base.html not found — skipping menu trim." -ForegroundColor DarkYellow
}

# 3) Ensure templates/courses.html if we added routes
if ($AddCourses) {
  $tplDir = Join-Path $AppDir "templates"
  if (-not (Test-Path $tplDir)) { New-Item -ItemType Directory $tplDir | Out-Null }
  $coursesTpl = Join-Path $tplDir "courses.html"
  if (-not (Test-Path $coursesTpl)) {
    Backup-File $coursesTpl
    $tpl = @'
{% extends 'base.html' %}
{% block content %}
<h3 class="mb-3">Courses (Training Recommender)</h3>
<div class="row">
  <div class="col-md-5">
    <div class="card p-3 mb-3">
      <h5>{{ 'Edit' if item else 'Add New' }}</h5>
      <form method="post">
        <div class="mb-2"><label class="form-label">Title</label>
          <input name="title" class="form-control" value="{{ item.title if item }}" required></div>
        <div class="mb-2"><label class="form-label">Competency</label>
          <select name="competency_id" class="form-select">
            {% for c in competencies %}
              <option value="{{ c.id }}" {% if item and item.competency_id==c.id %}selected{% endif %}>{{ c.name }}</option>
            {% endfor %}
          </select></div>
        <div class="mb-2"><label class="form-label">Min Level (L0–L4)</label>
          <select name="min_level" class="form-select">
            {% for i in range(5) %}
              <option value="{{ i }}" {% if item and item.min_level==i %}selected{% endif %}>L{{ i }}</option>
