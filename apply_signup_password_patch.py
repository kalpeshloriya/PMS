import os, re, io, datetime, shutil

APP = 'app.py'
BASE = os.path.join('templates','base.html')
TEAM = os.path.join('templates','team_members.html')
SIGNUP = os.path.join('templates','signup.html')

ANCHOR = re.compile(r'(?m)^(?:@app\.route|def\s+|class\s+|#\s*----|\Z)')

ROUTE_STARTS = [
    r"(?m)^@app\.route\('/admin/team',",
]
FUNC_NAMES   = [r"(?m)^def\s+team_members\s*\("]

SIGNUP_ROUTE = r"(?m)^@app\.route\('/signup'"


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
    with io.open(p,'w',encoding='utf-8',newline='\n') as f:
        f.write(s)

# ------------------ content blocks ------------------
TEAM_ROUTE_BLOCK = """
@app.route('/admin/team', methods=['GET','POST'])
@login_required
@require_roles('ADMIN')
def team_members():
    # Dropdown data
    groups = Group.query.order_by(Group.name).all()
    grades = Grade.query.order_by(Grade.name).all()
    roles  = Role.query.order_by(Role.name).all()

    mgr_flagged = User.query.filter_by(is_manager=True).all()
    admins      = User.query.filter_by(app_role='ADMIN').all()
    managers = list({u.id: u for u in (mgr_flagged + admins)}.values())

    edit_id = request.args.get('edit_id', type=int)
    item = db.session.get(User, edit_id) if edit_id else None

    if request.method == 'POST':
        data = request.form
        creating = item is None

        if creating:
            username = (data.get('username') or '').strip()
            if not username:
                flash('Username is required', 'danger')
                return redirect(url_for('team_members'))
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('team_members'))
            item = User(username=username)
            db.session.add(item)

        before = dict(item.__dict__)

        # basic fields
        item.full_name = data.get('full_name') or None
        item.email = data.get('email') or None

        def parse_bool(v):
            return str(v).strip().lower() in ('1','true','yes','y','on')
        item.is_manager = parse_bool(data.get('is_manager','false'))

        # app role guard (cannot demote last admin)
        new_app_role = data.get('app_role') or item.app_role or 'EMPLOYEE'
        if item.app_role == 'ADMIN' and new_app_role != 'ADMIN':
            remaining_admins = User.query.filter(User.app_role=='ADMIN', User.id!=item.id).count()
            if remaining_admins == 0:
                flash('Cannot demote the LAST admin user.', 'danger')
                return redirect(url_for('team_members'))
        item.app_role = new_app_role

        # passwords
        pwd = data.get('password') or ''
        cpw = data.get('confirm_password') or ''
        if creating:
            if len(pwd) < 8:
                flash('Password must be at least 8 characters for new user.', 'danger')
                return redirect(url_for('team_members'))
            if pwd != cpw:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('team_members'))
            if hasattr(item,'set_password'):
                item.set_password(pwd)
            else:
                from werkzeug.security import generate_password_hash
                item.password_hash = generate_password_hash(pwd)
        else:
            if pwd:
                if len(pwd) < 8:
                    flash('New password must be at least 8 characters.', 'danger')
                    return redirect(url_for('team_members', edit_id=item.id))
                if pwd != cpw:
                    flash('New passwords do not match.', 'danger')
                    return redirect(url_for('team_members', edit_id=item.id))
                if hasattr(item,'set_password'):
                    item.set_password(pwd)
                else:
                    from werkzeug.security import generate_password_hash
                    item.password_hash = generate_password_hash(pwd)

        def to_int_or_none(val):
            s = (val or '').strip()
            return int(s) if s.isdigit() else None

        item.group_id   = to_int_or_none(data.get('group_id'))
        item.grade_id   = to_int_or_none(data.get('grade_id'))
        item.role_id    = to_int_or_none(data.get('role_id'))
        item.manager_id = to_int_or_none(data.get('manager_id'))

        db.session.commit()
        log_audit('UPSERT','User', item.id, before=before, after=item.__dict__)
        flash('Saved team member', 'success')
        return redirect(url_for('team_members'))

    rows = User.query.order_by(User.id).all()
    return render_template('team_members.html', rows=rows, item=item,
                           groups=groups, grades=grades, roles=roles, managers=managers)
"""

SIGNUP_ROUTE_BLOCK = """
@app.route('/signup', methods=['GET','POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email    = (request.form.get('email') or '').strip()
        pwd      = request.form.get('password') or ''
        cpw      = request.form.get('confirm_password') or ''

        if not username:
            error = 'Username is required.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already exists.'
        elif not email:
            error = 'Email is required.'
        elif len(pwd) < 8:
            error = 'Password must be at least 8 characters.'
        elif pwd != cpw:
            error = 'Passwords do not match.'

        if not error:
            u = User(username=username, email=email, full_name=None,
                     is_manager=False, app_role='EMPLOYEE')
            if hasattr(u,'set_password'):
                u.set_password(pwd)
            else:
                from werkzeug.security import generate_password_hash
                u.password_hash = generate_password_hash(pwd)
            db.session.add(u)
            db.session.commit()
            log_audit('CREATE','User', u.id, after=u.__dict__)
            flash('Signup successful. Please log in.', 'success')
            return redirect(url_for('login'))
        flash(error, 'danger')

    return render_template('signup.html')
"""

TEAM_TEMPLATE = """{% extends 'base.html' %}
{% block content %}
<h3 class="mb-3">Team Members</h3>
<div class="row">
  <div class="col-md-5">
    <div class="card p-3 mb-3">
      <h5>{{ 'Edit' if item else 'Add New' }}</h5>
      <form method="post">
        <div class="mb-2"><label class="form-label">Username</label>
          <input name="username" class="form-control" value="{{ item.username if item }}" {% if item %}readonly{% endif %} required></div>
        <div class="mb-2"><label class="form-label">Full Name</label>
          <input name="full_name" class="form-control" value="{{ item.full_name if item }}"></div>
        <div class="mb-2"><label class="form-label">Email</label>
          <input name="email" class="form-control" value="{{ item.email if item }}"></div>
        <div class="mb-2"><label class="form-label">Is Manager</label>
          <select name="is_manager" class="form-select">
            <option value="false" {% if item and not item.is_manager %}selected{% endif %}>No</option>
            <option value="true"  {% if item and item.is_manager %}selected{% endif %}>Yes</option>
          </select></div>
        <div class="mb-2"><label class="form-label">App Role</label>
          {% set roles_list = ['EMPLOYEE','MANAGER','ADMIN','HRBP','TOWER_LEAD','PRACTICE_HEAD'] %}
          <select name="app_role" class="form-select">
            {% for r in roles_list %}<option value="{{ r }}" {% if item and item.app_role==r %}selected{% endif %}>{{ r }}</option>{% endfor %}
          </select></div>
        <div class="mb-2"><label class="form-label">Password {% if item %}(leave blank to keep){% else %}(min 8 chars){% endif %}</label>
          <input name="password" type="password" class="form-control" {% if not item %}required{% endif %} minlength="8"></div>
        <div class="mb-3"><label class="form-label">Confirm Password</label>
          <input name="confirm_password" type="password" class="form-control" {% if not item %}required{% endif %} minlength="8"></div>
        <div class="mb-2"><label class="form-label">Group</label>
          <select name="group_id" class="form-select">
            <option value="">- None -</option>
            {% for g in groups %}<option value="{{ g.id }}" {% if item and item.group_id==g.id %}selected{% endif %}>{{ g.name }}</option>{% endfor %}
          </select></div>
        <div class="mb-2"><label class="form-label">Grade</label>
          <select name="grade_id" class="form-select">
            <option value="">- None -</option>
            {% for g in grades %}<option value="{{ g.id }}" {% if item and item.grade_id==g.id %}selected{% endif %}>{{ g.name }}</option>{% endfor %}
          </select></div>
        <div class="mb-2"><label class="form-label">Role</label>
          <select name="role_id" class="form-select">
            <option value="">- None -</option>
            {% for r in roles %}<option value="{{ r.id }}" {% if item and item.role_id==r.id %}selected{% endif %}>{{ r.name }}</option>{% endfor %}
          </select></div>
        <div class="mb-3"><label class="form-label">Manager</label>
          <select name="manager_id" class="form-select">
            <option value="">- None -</option>
            {% for m in managers %}<option value="{{ m.id }}" {% if item and item.manager_id==m.id %}selected{% endif %}>{{ m.full_name or m.username }}{% if m.app_role=='ADMIN' %} (ADMIN){% elif m.is_manager %} (Manager){% endif %}</option>{% endfor %}
          </select></div>
        <button class="btn btn-primary">{{ 'Update' if item else 'Create' }}</button>
        {% if item %}<a class="btn btn-secondary" href="{{ url_for('team_members') }}">Cancel</a>{% endif %}
      </form>
    </div>
  </div>
  <div class="col-md-7">
    <div class="card p-3">
      <h5>All</h5>
      <table class="table table-striped table-hover">
        <thead>
          <tr>
            <th>ID</th><th>Username</th><th>Name</th><th>Email</th>
            <th>App Role</th><th>IsMgr</th><th>Group</th><th>Grade</th><th>Role</th><th>Manager</th><th></th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td>{{ row.id }}</td>
            <td>{{ row.username }}</td>
            <td>{{ row.full_name or '-' }}</td>
            <td>{{ row.email or '-' }}</td>
            <td>{{ row.app_role }}</td>
            <td>{{ 'Yes' if row.is_manager else 'No' }}</td>
            <td>{{ row.group.name if row.group else '-' }}</td>
            <td>{{ row.grade.name if row.grade else '-' }}</td>
            <td>{{ row.role.name if row.role else '-' }}</td>
            <td>{% if row.manager %}{{ row.manager.full_name or row.manager.username }}{% elif row.manager_id %}ID {{ row.manager_id }}{% else %}-{% endif %}</td>
            <td>
              <a class="btn btn-sm btn-primary" href="{{ url_for('team_members', edit_id=row.id) }}">Edit</a>
              <a class="btn btn-sm btn-danger" href="{{ url_for('team_members_delete', id=row.id) }}" onclick="return confirm('Delete?');">Delete</a>
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

SIGNUP_TEMPLATE = """{% extends 'base.html' %}
{% block content %}
<h3 class="mb-3">Sign up</h3>
<div class="row">
  <div class="col-md-6 col-lg-5">
    <div class="card p-3">
      <form method="post" autocomplete="off">
        <div class="mb-2"><label class="form-label">Username *</label>
          <input name="username" class="form-control" required></div>
        <div class="mb-2"><label class="form-label">Email *</label>
          <input name="email" type="email" class="form-control" required></div>
        <div class="mb-2"><label class="form-label">Password *</label>
          <input name="password" type="password" class="form-control" minlength="8" required></div>
        <div class="mb-3"><label class="form-label">Confirm Password *</label>
          <input name="confirm_password" type="password" class="form-control" minlength="8" required></div>
        <button class="btn btn-primary w-100">Create account</button>
        <div class="mt-3">Already have an account? <a href="{{ url_for('login') }}">Login</a></div>
      </form>
    </div>
  </div>
</div>
{% endblock %}
"""

# ------------------ helpers ------------------

def remove_blocks(src, starts_regex_list, func_regex_list):
    ranges=[]
    for pat in starts_regex_list:
        for m in re.finditer(pat, src):
            s=m.start(); tail=src[s+1:]
            m2=ANCHOR.search(tail)
            e=(s+1+m2.start()) if m2 else len(src)
            ranges.append((s,e))
    for pat in func_regex_list:
        for m in re.finditer(pat, src):
            s=m.start(); tail=src[s+1:]
            m2=ANCHOR.search(tail)
            e=(s+1+m2.start()) if m2 else len(src)
            ranges.append((s,e))
    if not ranges:
        return src, 0
    ranges=sorted(ranges)
    merged=[]
    for s,e in ranges:
        if not merged or s>merged[-1][1]:
            merged.append((s,e))
        else:
            merged[-1]=(merged[-1][0], max(merged[-1][1], e))
    for s,e in reversed(merged):
        src=src[:s]+src[e:]
    return src, len(merged)


def ensure_imports_and_db_shim(src:str)->str:
    # ensure werkzeug.security import
    if 'from werkzeug.security import generate_password_hash' not in src:
        # add near other imports
        m = re.search(r'(?m)^from flask .*$', src)
        ins = "\nfrom werkzeug.security import generate_password_hash, check_password_hash"
        if m:
            idx = m.end()
            src = src[:idx] + ins + src[idx:]
        else:
            src = ins + "\n" + src

    # ensure user methods exist? (we can't reliably inject methods into class); handled at runtime by hasattr

    # DB shim for password_hash (SQLite)
    shim = """
with app.app_context():
    try:
        rows = db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()
        cols = [r[1] for r in rows]
        if 'password_hash' not in cols:
            db.session.execute(db.text("ALTER TABLE user ADD COLUMN password_hash TEXT"))
            db.session.commit()
    except Exception:
        pass
"""
    if 'PRAGMA table_info(user)' not in src and 'password_hash' not in src:
        # insert shim after app initialization
        m_app = re.search(r"(?m)^app\s*=\s*Flask\(.*\)$", src)
        if m_app:
            idx = m_app.end()
            src = src[:idx] + "\n\n" + shim + src[idx:]
        else:
            src = src + "\n\n" + shim
    return src


def upsert_team_route(src:str)->str:
    src, removed = remove_blocks(src, ROUTE_STARTS, FUNC_NAMES)
    print(f"[info] removed {removed} existing team_members blocks")
    if not src.endswith('\n'): src+='\n'
    src += "\n\n# --- Team Members (password aware, last-admin guarded) ---\n" + TEAM_ROUTE_BLOCK + "\n"
    return src


def upsert_signup_route(src:str)->str:
    # remove existing signup blocks
    ranges=[]
    for m in re.finditer(SIGNUP_ROUTE, src):
        s=m.start(); tail=src[s+1:]
        m2=ANCHOR.search(tail)
        e=(s+1+m2.start()) if m2 else len(src)
        ranges.append((s,e))
    if ranges:
        for s,e in reversed(ranges):
            src=src[:s]+src[e:]
        print(f"[info] removed {len(ranges)} existing signup blocks")
    if not src.endswith('\n'): src+='\n'
    src += "\n\n# --- Public Signup (username, email, password) ---\n" + SIGNUP_ROUTE_BLOCK + "\n"
    return src


def patch_navbar_signup_link():
    if not os.path.exists(BASE):
        print('[warn] base.html not found; skipping nav link')
        return

    backup(BASE)
    html = read_txt(BASE)

    # If a signup link already exists, do nothing
    import re
    if re.search(r"href=\"\{\{\s*(safe_url_for|url_for)\('signup'\)\s*\}\}\"", html, flags=re.IGNORECASE):
        print('[info] base.html already has a signup link; leaving as-is')
        return

    # Decide helper: prefer safe_url_for if already present in base.html
    helper = 'safe_url_for' if 'safe_url_for(' in html else 'url_for'

    # Build the nav item without using % formatting (to avoid conflicts with Jinja’s {% ... %})
    nav_item = (
        "\n{% if not current_user.is_authenticated %}\n"
        '<li class="nav-item"><a class="nav-link" href="{{ ' + helper + "('signup') }}\">Sign up</a></li>\n"
        "{% endif %}\n"
    )

    # Insert before the first closing </ul> (commonly the end of the navbar <ul>)
    new_html, n = re.subn(r'</ul>', nav_item + '</ul>', html, count=1, flags=re.IGNORECASE)
    if n == 0:
        # Fallback: append to the end of file
        new_html = html + "\n" + nav_item

    write_txt(BASE, new_html)
    print('[ok] navbar signup link added (or appended)')
def apply_patch():
    if not os.path.exists(APP): raise SystemExit('app.py not found')
    backup(APP)
    src = read_txt(APP)
    src = ensure_imports_and_db_shim(src)
    src = upsert_team_route(src)
    src = upsert_signup_route(src)
    write_txt(APP, src)
    print('[done] app.py patched')

    # write templates
    if os.path.exists(TEAM): backup(TEAM)
    write_txt(TEAM, TEAM_TEMPLATE)
    print('[done] templates/team_members.html written')

    write_txt(SIGNUP, SIGNUP_TEMPLATE)
    print('[done] templates/signup.html written')

    patch_navbar_signup_link()
    print('\nPatch complete.')

if __name__ == '__main__':
    apply_patch()
