# PMS Advanced – Windows Quick Start

## One-click (PowerShell)
```
.un.ps1
```

## Manual
```
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:FLASK_APP = "app.py"
python -m flask run
```
