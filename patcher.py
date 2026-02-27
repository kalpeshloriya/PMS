import os, re, io, datetime, shutil

APP_PATH = os.path.abspath("app.py")
TPL_DIR = os.path.join("templates")
BASE_PATH = os.path.join(TPL_DIR, "base.html")
COURSES_TPL_PATH = os.path.join(TPL_DIR, "courses.html")
TEAM_MEMBERS_TPL_PATH = os.path.join(TPL_DIR, "team_members.html")

def backup(path):
    if not os.path.exists(path): return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, f"{path}.{ts}.bak")
    print(f"[backup] {path} -> {path}.{ts}.bak")

def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def replace_function(content, func_name, new_block):
    m = re.search(rf"(?m)^def\s+{re.escape(func_name)}\s*\(", content)
    if not m:
        print(f"[warn] function {func_name} not found; skipping")
        return content
    start = m.start()
    after = content[m.end():]
    # Next top-level anchor
    m2 = re.search(r"(?m)^(def\s+|@app\.route|class\s+|#\s*----|\Z)", after)
    end = m.end() + (m2.start() if m2 else len(after))
    before = content[:start]
    tail = content[end:]
    new_block = new_block.rstrip() + "\n"
    print(f"[ok] replaced function {func_name}")
    return before + new_block + "\n\n" + tail

def ensure_courses_routes(content):
    if re.search(r"(?m)^def\s+courses\s*\(", content):
        print("[info] courses() route already exists")
        return content, False
    routes = '''
@app.route('/admin/courses', methods=['GET','POST'])
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
'''.strip("\n")
    if "# Flask 3 safe init" in content:
        content = content.replace("# Flask 3 safe init", routes + "\n\n# Flask 3 safe init")
    else:
        content = content + "\n\n" + routes + "\n"
    print("[ok] injected courses() routes")
    return content, True

def ensure_courses_template():
    if os.path.exists(COURSES_TPL_PATH):
        print("[info] templates/courses.html already exists")
        return
    tpl = """{% extends 'base.html' %}
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
            {% endfor %}
          </select></div>

        <div class="mb-2"><label class="form-label">LMS Course ID</label>
          <input name="external_id" class="form-control" value="{{ item.external_id if item }}"></div>

        <div class="mb-2"><label class="form-label">Direct URL</label>
          <input name="url" class="form-control" value="{{ item.url if item }}"></div>

        <button class="btn btn-primary">{{ 'Update' if item else 'Create' }}</button>
        {% if item %} <a class="btn btn-secondary" href="{{ url_for('courses') }}">Cancel</a> {% endif %}
      </form>
    </div>
  </div>

  <div class="col-md-7">
    <div class="card p-3">
      <h5>All Courses</h5>
      <table class="table table-striped">
        <thead><tr><th>ID</th><th>Title</th><th>Competency</th><th>Min</th><th>Link</th><th></th></tr></thead>
        <tbody>
          {% for c in rows %}
          <tr>
            <td>{{ c.id }}</td>
            <td>{{ c.title }}</td>
            <td>{{ c.competency.name if c.competency else '-' }}</td>
            <td>L{{ c.min_level }}</td>
            <td>{% if c.url %}<a class="btn btn-sm btn-secondary" href="{{ c.url }}" target="_blank">Open</a>{% endif %}</td>
            <td>
              <a class="btn btn-sm btn-primary" href="{{ url_for('courses', edit_id=c.id) }}">Edit</a>
              <a class="btn btn-sm btn-danger" href="{{ url_for('courses_delete', id=c.id) }}" onclick="return confirm('Delete?')">Delete</a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
"""
    write_text(COURSES_TPL_PATH, tpl)
    print("[ok] templates/courses.html created")

def ensure_team_members_template():
    if os.path.exists(TEAM_MEMBERS_TPL_PATH):
        print("[info] templates/team_members.html already exists")
        return
    tpl = """{% extends 'base.html' %}
{% block content %}
<h3 class="mb-3">Team Members</h3>
<div class="row">
  <div class="col-md-5">
    <div class="card p-3 mb-3">
      <h5>{{ 'Edit' if item else 'Add New' }}</h5>
      <form method="post">
        <div class="mb-2"><label class="form-label">Username</label>
          <input name="username" class="form-control" value="{{ item.username if item }}" {% if item %}readonly{% endif %}></div>
        <div class="mb-2"><label class="form-label">Full Name</label>
          <input name="full_name" class="form-control" value="{{ item.full_name if item }}"></div>
        <div class="mb-2"><label class="form-label">Email</label>
          <input name="email" class="form-control" value="{{ item.email if item }}"></div>
        <div class="mb-2"><label class="form-label">Is Manager (true/false)</label>
          <input name="is_manager" class="form-control" value="{{ item.is_manager if item }}"></div>
        <div class="mb-2"><label class="form-label">App Role</label>
          <input name="app_role" class="form-control" value="{{ item.app_role if item }}"></div>
        <div class="mb-2"><label class="form-label">Group ID</label>
          <input name="group_id" class="form-control" value="{{ item.group_id if item }}"></div>
        <div class="mb-2"><label class="form-label">Grade ID</label>
          <input name="grade_id" class="form-control" value="{{ item.grade_id if item }}"></div>
        <div class="mb-2"><label class="form-label">Role ID</label>
          <input name="role_id" class="form-control" value="{{ item.role_id if item }}"></div>
        <div class="mb-2"><label class="form-label">Manager ID</label>
          <input name="manager_id" class="form-control" value="{{ item.manager_id if item }}"></div>
        <button class="btn btn-primary">{{ 'Update' if item else 'Create' }}</button>
        {% if item %} <a class="btn btn-secondary" href="{{ url_for('team_members') }}">Cancel</a> {% endif %}
      </form>
    </div>
  </div>

  <div class="col-md-7">
    <div class="card p-3">
      <h5>All</h5>
      <table class="table table-striped">
        <thead>
          <tr>
            <th>ID</th><th>Username</th><th>Full Name</th><th>Email</th><th>Role</th><th>Is Mgr</th><th>Grp</th><th>Grd</th><th>Role</th><th>Mgr</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td>{{ row.id }}</td>
            <td>{{ row.username }}</td>
            <td>{{ row.full_name }}</td>
            <td>{{ row.email }}</td>
            <td>{{ row.app_role }}</td>
            <td>{{ 'Yes' if row.is_manager else 'No' }}</td>
            <td>{{ row.group_id or '-' }}</td>
            <td>{{ row.grade_id or '-' }}</td>
            <td>{{ row.role_id or '-' }}</td>
            <td>{{ row.manager_id or '-' }}</td>
            <td>
              <a class="btn btn-sm btn-primary" href="{{ url_for('team_members', edit_id=row.id) }}">Edit</a>
              <a class="btn btn-sm btn-danger" href="{{ url_for('team_members_delete', id=row.id) }}" onclick="return confirm('Delete?')">Delete</a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
"""
    write_text(TEAM_MEMBERS_TPL_PATH, tpl)
    print("[ok] templates/team_members.html created (fallback)")

def trim_base_menu(app_src):
    if not os.path.exists(BASE_PATH):
        print("[warn] templates/base.html not found; skipping menu trim")
        return
    backup(BASE_PATH)
    base = read_text(BASE_PATH)
    # If routes missing, remove their menu items to avoid BuildError
    if not re.search(r"(?m)^def\s+import_export\s*\(", app_src):
        base = re.sub(r"(?m)^\s*<li>.*url_for\('import_export'\).*\r?\n", "", base)
    if not re.search(r"(?m)^def\s+calibration\s*\(", app_src):
        base = re.sub(r"(?m)^\s*<li>.*url_for\('calibration'\).*\r?\n", "", base)
    write_text(BASE_PATH, base)
    print("[done] base.html trimmed (if needed)")

def patch_app():
    backup(APP_PATH)
    src = read_text(APP_PATH)

    # Teams helper — no f-strings
    safe_teams = r'''
def send_teams_card(title, text):
    if not TEAMS_WEBHOOK_URL:
        return False
    try:
        payload = {"text": "**" + str(title) + "**\n\n" + str(text)}
        requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=5)
        return True
    except Exception:
        return False
'''.strip("\n")
    src = replace_function(src, "send_teams_card", safe_teams)

    # Self review — triple-quoted .format email
    safe_self = r'''
@app.route('/review/self', methods=['GET','POST'])
@login_required
def self_review():
    user = current_user
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
                user_id=user.id, competency_id=c.id,
                level=int(val), cycle_id=sel_cycle_id, comment=(cmt or None)
            ))
            saved_any = True

        if saved_any:
            db.session.commit()
            log_audit('UPSERT','SelfEvaluation', None, after={'user_id':user.id,'cycle_id':sel_cycle_id})

            mgr = db.session.get(User, getattr(user, 'manager_id', None)) if getattr(user, 'manager_id', None) else None
            if mgr and getattr(mgr, 'email', None):
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
            'competency': c, 'expected': expected, 'self_level': self_level,
            'gap': gap, 'weighted_gap': weighted_gap,
            'courses': courses[:3], 'self_comment': self_comment
        })
    return render_template('self_review.html', competencies=competencies, rows=rows, cycles=cycles, sel_cycle_id=sel_cycle_id)
'''.strip("\n")
    src = replace_function(src, "self_review", safe_self)

    # Manager review — triple-quoted .format email
    safe_mgr = r'''
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
                user_id=sel_user.id, manager_id=current_user.id, competency_id=c.id,
                level=int(val), cycle_id=sel_cycle_id, comment=(cmt or None)
            ))
            saved_any = True

        if saved_any:
            db.session.commit()
            log_audit('UPSERT','ManagerEvaluation', None, after={'user_id':sel_user.id,'cycle_id':sel_cycle_id})

        # Notify employee
            if getattr(sel_user, 'email', None):
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
                'competency': c, 'expected': expected,
                'self_level': self_map.get(c.id, {}).get('level'),
                'self_comment': self_map.get(c.id, {}).get('comment'),
                'manager_level': man_lvls.get(c.id, 0),
                'gap': gap, 'weighted_gap': weighted_gap,
                'courses': courses[:3]
            })

    return render_template('manager_review.html', team=team, sel_user=sel_user, rows=rows, cycles=cycles, sel_cycle_id=sel_cycle_id)
'''.strip("\n")
    src = replace_function(src, "manager_review", safe_mgr)

    # Courses routes (if missing)
    src, added_courses = ensure_courses_routes(src)

    write_text(APP_PATH, src)
    print("[done] app.py patched")

    # Trim menu for undefined endpoints (import_export, calibration)
    trim_base_menu(src)

    # Ensure templates
    ensure_team_members_template()
    if added_courses:
        ensure_courses_template()

if __name__ == "__main__":
    patch_app()
    print("\nPatch completed successfully.")