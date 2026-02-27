
# Render Fast-Deploy Add-on (for your existing PMS repo)

This package lets you deploy **fast** on Render Free tier by skipping heavy build deps.

## What’s inside
- `requirements-render.txt` – lightweight deps (no pandas/openpyxl)
- `Procfile` – `web: gunicorn app:app`
- `render.yaml` – one-click Render config using the light requirements

## How to use
1) Add these three files to the **root** of your existing PMS repository (where `app.py` lives). Commit & push.

2) On Render:
   - Create **New Web Service** from this GitHub repo
   - If you don’t use `render.yaml`, set manually:
     - Build Command: `pip install -r requirements-render.txt`
     - Start Command: `gunicorn app:app`
   - Plan: **Free**

3) First deploy should complete in **~1–3 minutes**.

> Note: This skips features that need `pandas`/`openpyxl` (CSV/Excel import/export). Your core app (auth, reviews, dashboards, UI) runs normally. If you later need full import/export on Render Free, switch to Docker deploy or Railway.

## Optional (health check)
If you want a quick health route, add this to `app.py`:
```python
@app.get('/healthz')
def healthz():
    return 'ok', 200
```
Then you can set Render Health Check Path to `/healthz`.

## Environment variables
Render will set `SECRET_KEY` from `render.yaml`. Add any SMTP variables in the Render **Environment** tab as needed.

