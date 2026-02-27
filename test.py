# 1) Create a tiny Python patch file safely (PowerShell here-string)
@'
import os, re, io, datetime, shutil

BASE = os.path.join('templates','base.html')

def backup(p):
    if os.path.exists(p):
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(p, f"{p}.{ts}.bak")
        print(f"[backup] {p} -> {p}.{ts}.bak")

def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()

def write(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)

if not os.path.exists(BASE):
    raise SystemExit("templates/base.html not found")

backup(BASE)
html = read(BASE)

# If a signup link already exists, do nothing
if re.search(r"href=\"\{\{\s*(safe_url_for|url_for)\('signup'\)\s*\}\}\"", html):
    print("[info] Signup link already present; no changes.")
else:
    helper = 'safe_url_for' if 'safe_url_for(' in html else 'url_for'
    nav_item = """
{% if not current_user.is_authenticated %}
<li class="nav-item"><a class="nav-link" href="{{ __HELPER__('signup') }}">Sign up</a></li>
{% endif %}
""".replace('__HELPER__', helper)

    # Insert before the first closing </ul> (navbar menu). If not found, append.
    new_html, n = re.subn(r'</ul>', nav_item + '</ul>', html, count=1, flags=re.IGNORECASE)
    if n == 0:
        new_html = html + "\n" + nav_item

    write(BASE, new_html)
    print("[ok] Navbar Signup link added.")

print("Done.")
'@ | Set-Content .\patch_nav_signup.py -Encoding UTF8

# 2) Run it with your venv Python
.\.venv\Scripts\python.exe .\patch_nav_signup.py

# 3) Clean up the helper file (optional)
Remove-Item .\patch_nav_signup.py -Force