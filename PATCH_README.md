
# One‑click Patch: Postgres Switch (Render‑ready)

This patch makes your app use **PostgreSQL in production** (via `DATABASE_URL`) and
**SQLite locally** (fallback), so your data becomes **permanent** on Render.

It also:
- Adds `psycopg2-binary` to your requirements file (the one Render builds from).
- Injects a small `/healthz` route (if missing) for quick health checks.
- Backs up changed files with a timestamped `.bak`.

## What the patch does
1) **app.py**
   - Inserts env‑first DB config **before** `db = SQLAlchemy(app)`:
     ```python
     import os
     db_url = os.getenv('DATABASE_URL')
     if db_url:
         db_url = db_url.replace('postgres://', 'postgresql://', 1)
     app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///pms.db'
     app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
     ```
   - Adds a tiny `/healthz` route if it doesn't exist.

2) **requirements**
   - Ensures `psycopg2-binary==2.9.9` is present in `requirements-render.txt` (if that file exists),
     otherwise it adds it to `requirements.txt`.

## How to apply
1) Unzip into your project **root** (same folder as `app.py`).
2) Run the patcher in your venv:

   **Windows (PowerShell)**
   ```powershell
   .\.venv\Scripts\Activate
   python apply_postgres_switch_patch.py
   ```

   **Linux/Mac**
   ```bash
   source .venv/bin/activate
   python apply_postgres_switch_patch.py
   ```
3) Verify locally:
   ```bash
   python -m py_compile app.py
   python -m flask run
   ```
   - Locally it will use **SQLite** (`pms.db`).
   - On Render (with `DATABASE_URL`), it will use **PostgreSQL**.

## Render steps
- In **Render Dashboard → Your Web Service → Environment**:
  - Set `DATABASE_URL` to your Render Postgres connection string (use the *Internal Connection String*).
- Deploy. Your data now lives in Postgres and **persists** across restarts/redeploys.

