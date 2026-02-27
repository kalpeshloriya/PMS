import os, re, io, datetime, shutil

APP = 'app.py'
REQ_RENDER = 'requirements-render.txt'
REQ_DEFAULT = 'requirements.txt'

DB_BLOCK = (
    "\n"
    "# --- Database configuration (env-first: Postgres on Render, SQLite locally) ---\n"
    "import os\n"
    "db_url = os.getenv('DATABASE_URL')\n"
    "if db_url:\n"
    "    db_url = db_url.replace('postgres://', 'postgresql://', 1)\n"
    "app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///pms.db'\n"
    "app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)\n"
)

HEALTHZ_BLOCK = (
    "\n"
    "# --- Health check endpoint ---\n"
    "@app.get('/healthz')\n"
    "def healthz():\n"
    "    return 'ok', 200\n"
)


def backup(path):
    if os.path.exists(path):
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(path, f"{path}.{ts}.bak")
        print(f"[backup] {path} -> {path}.{ts}.bak")


def read_text(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def ensure_psycopg():
    target = REQ_RENDER if os.path.exists(REQ_RENDER) else REQ_DEFAULT
    if not os.path.exists(target):
        print(f"[warn] {target} not found; creating it")
        write_text(target, '')
    txt = read_text(target)
    if re.search(r'^psycopg2-binary\b', txt, re.MULTILINE):
        print(f"[ok] psycopg2-binary already present in {target}")
        return
    backup(target)
    if not txt.endswith('\n'):
        txt += '\n'
    txt += 'psycopg2-binary==2.9.9\n'
    write_text(target, txt)
    print(f"[ok] added psycopg2-binary to {target}")


def patch_app_py():
    if not os.path.exists(APP):
        raise SystemExit('app.py not found')
    backup(APP)
    src = read_text(APP)

    # Find app = Flask(...) and db = SQLAlchemy(app)
    m_app = re.search(r"(?m)^\s*app\s*=\s*Flask\(.*\)$", src)
    if not m_app:
        raise SystemExit("Could not find 'app = Flask(...)' in app.py")
    idx_app_end = m_app.end()

    m_db = re.search(r"(?m)^\s*db\s*=\s*SQLAlchemy\(\s*app\s*\)\s*$", src)
    if not m_db:
        # try a broader pattern
        m_db = re.search(r"SQLAlchemy\(\s*app\s*\)", src)
    if not m_db:
        print("[warn] Could not find 'db = SQLAlchemy(app)'; inserting DB config right after app init")
        insert_pos = idx_app_end
    else:
        insert_pos = m_db.start()  # ensure we set config before SQLAlchemy binds

    # Remove any existing direct SQLALCHEMY_DATABASE_URI assignments to avoid conflicts
    # We'll strip simple lines like: app.config['SQLALCHEMY_DATABASE_URI'] = ...
    src = re.sub(r"(?m)^\s*app\.config\['SQLALCHEMY_DATABASE_URI'\]\s*=.*$", "", src)

    # Insert our DB block if not already present
    if 'Database configuration (env-first' not in src:
        src = src[:insert_pos] + DB_BLOCK + "\n" + src[insert_pos:]
        print('[ok] inserted env-first DB config before SQLAlchemy init')
    else:
        print('[info] DB block already present; left as-is')

    # Add /healthz if missing
    if "/healthz" not in src:
        # append at EOF
        if not src.endswith('\n'):
            src += '\n'
        src += HEALTHZ_BLOCK + '\n'
        print('[ok] added /healthz endpoint')
    else:
        print('[info] /healthz already present')

    write_text(APP, src)
    print('[done] app.py patched')


def main():
    ensure_psycopg()
    patch_app_py()
    print('\nPatch complete. Now set DATABASE_URL in your Render service and redeploy.')

if __name__ == '__main__':
    main()
