import os, re, io, datetime, shutil

APP='app.py'
TPL='templates/team_members.html'

# Construct route block
route_block = []
route_block += ["@app.route('/admin/team', methods=['GET','POST'])"]
route_block += ["@login_required"]
route_block += ["@require_roles('ADMIN')"]
route_block += ["def team_members():"]
route_block += ["    groups = Group.query.order_by(Group.name).all()"]
route_block += ["    grades = Grade.query.order_by(Grade.name).all()"]
route_block += ["    roles  = Role.query.order_by(Role.name).all()"]
route_block += ["    mgr_flagged = User.query.filter_by(is_manager=True).all()"]
route_block += ["    admins      = User.query.filter_by(app_role='ADMIN').all()"]
route_block += ["    managers_map = {u.id: u for u in (mgr_flagged + admins)}"]
route_block += ["    managers = list(managers_map.values())"]
route_block += ["    edit_id = request.args.get('edit_id', type=int)"]
route_block += ["    item = User.query.get(edit_id) if edit_id else None"]
route_block += ["    if request.method == 'POST':"]
route_block += ["        data = request.form"]
route_block += ["        creating = item is None"]
route_block += ["        if creating:"]
route_block += ["            username = (data.get('username') or '').strip()"]
route_block += ["            if not username:"]
route_block += ["                flash('Username is required', 'danger')"]
route_block += ["                return redirect(url_for('team_members'))"]
route_block += ["            if User.query.filter_by(username=username).first():"]
route_block += ["                flash('Username already exists', 'danger')"]
route_block += ["                return redirect(url_for('team_members'))"]
route_block += ["            item = User(username=username)"]
route_block += ["            item.set_password('Password123!')"]
route_block += ["            db.session.add(item)"]
route_block += ["        before = item.__dict__.copy()"]
route_block += ["        item.full_name = data.get('full_name') or None"]
route_block += ["        item.email = data.get('email') or None"]
route_block += ["        item.is_manager = parse_bool(data.get('is_manager','false'))"]
route_block += ["        new_role = data.get('app_role') or item.app_role or 'EMPLOYEE'"]
route_block += ["        if item.app_role == 'ADMIN' and new_role != 'ADMIN':"]
route_block += ["            remaining_admins = User.query.filter(User.app_role=='ADMIN', User.id != item.id).count()"]
route_block += ["            if remaining_admins == 0:"]
route_block += ["                flash('Cannot demote the LAST admin user.', 'danger')"]
route_block += ["                return redirect(url_for('team_members'))"]
route_block += ["        item.app_role = new_role"]
route_block += ["        def to_int_or_none(val):"]
route_block += ["            if val is None: return None"]
route_block += ["            val = str(val).strip()"]
route_block += ["            return int(val) if val.isdigit() else None"]
route_block += ["        item.group_id   = to_int_or_none(data.get('group_id'))"]
route_block += ["        item.grade_id   = to_int_or_none(data.get('grade_id'))"]
route_block += ["        item.role_id    = to_int_or_none(data.get('role_id'))"]
route_block += ["        item.manager_id = to_int_or_none(data.get('manager_id'))"]
route_block += ["        db.session.commit()"]
route_block += ["        log_audit('UPSERT','User', item.id, before=before, after=item.__dict__)"]
route_block += ["        flash('Saved team member', 'success')"]
route_block += ["        return redirect(url_for('team_members'))"]
route_block += ["    rows = User.query.order_by(User.id).all()"]
route_block += ["    return render_template('team_members.html', rows=rows, item=item, groups=groups, grades=grades, roles=roles, managers=managers)"]
route_block += [""]
route_block += ["@app.route('/admin/team/delete/<int:id>')"]
route_block += ["@login_required"]
route_block += ["@require_roles('ADMIN')"]
route_block += ["def team_members_delete(id):"]
route_block += ["    u = User.query.get_or_404(id)"]
route_block += ["    if u.app_role == 'ADMIN':"]
route_block += ["        remaining_admins = User.query.filter(User.app_role=='ADMIN', User.id != u.id).count()"]
route_block += ["        if remaining_admins == 0:"]
route_block += ["            flash('Cannot delete the LAST admin user.', 'danger')"]
route_block += ["            return redirect(url_for('team_members'))"]
route_block += ["    before = u.__dict__.copy()"]
route_block += ["    db.session.delete(u)"]
route_block += ["    db.session.commit()"]
route_block += ["    log_audit('DELETE','User', id, before=before)"]
route_block += ["    flash('Deleted', 'success')"]
route_block += ["    return redirect(url_for('team_members'))"]

# Template content as lines (ASCII only)
team_tpl_lines = [
    '{% extends "base.html" %}',
    '{% block content %}',
    '<h3 class="mb-3">Team Members</h3>',
    '<div class="row">',
    '  <div class="col-md-5">',
    '    <div class="card p-3 mb-3">',
    '      <h5>{{ 'Edit' if item else 'Add New' }}</h5>',
    '      <form method="post">',
    '        <div class="mb-2"><label class="form-label">Username</label>',
    '          <input name="username" class="form-control" value="{{ item.username if item }}" {% if item %}readonly{% endif %} required></div>',
    '        <div class="mb-2"><label class="form-label">Full Name</label>',
    '          <input name="full_name" class="form-control" value="{{ item.full_name if item }}"></div>',
    '        <div class="mb-2"><label class="form-label">Email</label>',
    '          <input name="email" class="form-control" value="{{ item.email if item }}"></div>',
    '        <div class="mb-2"><label class="form-label">Is Manager</label>',
    '          <select name="is_manager" class="form-select">',
    '            <option value="false" {% if item and not item.is_manager %}selected{% endif %}>No</option>',
    '            <option value="true"  {% if item and item.is_manager %}selected{% endif %}>Yes</option>',
    '          </select></div>',
    '        <div class="mb-2"><label class="form-label">App Role</label>',
    '          {% set roles_list = ['EMPLOYEE','MANAGER','ADMIN','HRBP','TOWER_LEAD','PRACTICE_HEAD'] %}',
    '          <select name="app_role" class="form-select">',
    '            {% for r in roles_list %}<option value="{{ r }}" {% if item and item.app_role==r %}selected{% endif %}>{{ r }}</option>{% endfor %}',
    '          </select></div>',
    '        <div class="mb-2"><label class="form-label">Group</label>',
    '          <select name="group_id" class="form-select">',
    '            <option value="">- None -</option>',
    '            {% for g in groups %}<option value="{{ g.id }}" {% if item and item.group_id==g.id %}selected{% endif %}>{{ g.name }}</option>{% endfor %}',
    '          </select></div>',
    '        <div class="mb-2"><label class="form-label">Grade</label>',
    '          <select name="grade_id" class="form-select">',
    '            <option value="">- None -</option>',
    '            {% for g in grades %}<option value="{{ g.id }}" {% if item and item.grade_id==g.id %}selected{% endif %}>{{ g.name }}</option>{% endfor %}',
    '          </select></div>',
    '        <div class="mb-2"><label class="form-label">Role</label>',
    '          <select name="role_id" class="form-select">',
    '            <option value="">- None -</option>',
    '            {% for r in roles %}<option value="{{ r.id }}" {% if item and item.role_id==r.id %}selected{% endif %}>{{ r.name }}</option>{% endfor %}',
    '          </select></div>',
    '        <div class="mb-3"><label class="form-label">Manager</label>',
    '          <select name="manager_id" class="form-select">',
    '            <option value="">- None -</option>',
    '            {% for m in managers %}<option value="{{ m.id }}" {% if item and item.manager_id==m.id %}selected{% endif %}>{{ m.full_name or m.username }}{% if m.app_role=='ADMIN' %} (ADMIN){% elif m.is_manager %} (Manager){% endif %}</option>{% endfor %}',
    '          </select></div>',
    '        <button class="btn btn-primary">{{ 'Update' if item else 'Create' }}</button>',
    '        {% if item %}<a class="btn btn-secondary" href="{{ url_for('team_members') }}">Cancel</a>{% endif %}',
    '      </form>',
    '    </div>',
    '  </div>',
    '  <div class="col-md-7">',
    '    <div class="card p-3">',
    '      <h5>All</h5>',
    '      <table class="table table-striped table-hover"><thead>',
    '        <tr><th>ID</th><th>Username</th><th>Name</th><th>Email</th><th>App Role</th><th>IsMgr</th><th>Group</th><th>Grade</th><th>Role</th><th>Manager</th><th></th></tr>',
    '      </thead><tbody>',
    '        {% for row in rows %}',
    '        <tr>',
    '          <td>{{ row.id }}</td><td>{{ row.username }}</td><td>{{ row.full_name or '-' }}</td><td>{{ row.email or '-' }}</td>',
    '          <td>{{ row.app_role }}</td><td>{{ 'Yes' if row.is_manager else 'No' }}</td>',
    '          <td>{{ row.group.name if row.group else '-' }}</td>',
    '          <td>{{ row.grade.name if row.grade else '-' }}</td>',
    '          <td>{{ row.role.name if row.role else '-' }}</td>',
    '          <td>{% set mgr = row.manager %}{% if mgr %}{{ mgr.full_name or mgr.username }}{% else %}-{% endif %}</td>',
    '          <td><a class=\"btn btn-sm btn-primary\" href=\"{{ url_for(\'team_members\', edit_id=row.id) }}\">Edit</a> <a class=\"btn btn-sm btn-danger\" href=\"{{ url_for(\'team_members_delete\', id=row.id) }}\" onclick=\"return confirm('Delete?');\">Delete</a></td>',
    '        </tr>',
    '        {% endfor %}',
    '      </tbody></table>',
    '    </div>',
    '  </div>',
    '</div>',
    '{% endblock %}',
]

ANCHOR = re.compile(r'(?m)^(?:@app\.route|def\s+|class\s+|#\s*----|\Z)')
ROUTE_STARTS = [r"(?m)^@app\.route\('/admin/team',", r"(?m)^@app\.route\('/admin/team/delete/<int:id>'"]
FUNC_NAMES   = [r"(?m)^def\s+team_members\s*\(", r"(?m)^def\s+team_members_delete\s*\("]

def backup(path):
    if os.path.exists(path):
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(path, f"{path}.{ts}.bak")
        print(f"[backup] {path} -> {path}.{ts}.bak")

def read_txt(p):
    with io.open(p,'r',encoding='utf-8') as f:
        return f.read()

def write_txt(p,s):
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    with io.open(p,'w',encoding='utf-8',newline='
') as f:
        f.write(s)

def remove_blocks(src):
    ranges=[]
    for pat in ROUTE_STARTS:
        for m in re.finditer(pat, src):
            s=m.start(); tail=src[s+1:]
            m2=ANCHOR.search(tail)
            e=(s+1+m2.start()) if m2 else len(src)
            ranges.append((s,e))
    for pat in FUNC_NAMES:
        for m in re.finditer(pat, src):
            s=m.start(); tail=src[s+1:]
            m2=ANCHOR.search(tail)
            e=(s+1+m2.start()) if m2 else len(src)
            ranges.append((s,e))
    if not ranges:
        return src
    ranges=sorted(ranges)
    merged=[]
    for s,e in ranges:
        if not merged or s>merged[-1][1]:
            merged.append((s,e))
        else:
            merged[-1]=(merged[-1][0], max(merged[-1][1], e))
    for s,e in reversed(merged):
        src=src[:s]+src[e:]
    print(f"[ok] removed {len(merged)} old team routes")
    return src

def apply_patch():
    if not os.path.exists(APP):
        raise SystemExit('app.py not found')
    backup(APP)
    src=read_txt(APP)
    src=remove_blocks(src)
    if not src.endswith('
'): src+='
'
    src += '

# --- Team Members (guarded last admin + dropdowns) ---
' + '
'.join(route_block) + '
'
    write_txt(APP, src)
    print('[done] app.py updated with guarded routes')
    # write template
    if os.path.exists(TPL): backup(TPL)
    write_txt(TPL, '
'.join(team_tpl_lines))
    print('[done] templates/team_members.html written')

if __name__=='__main__':
    apply_patch()