import os, re, io, datetime, shutil

ROOT_TPL = 'templates'

SIGNUP_REGEX = re.compile(r"href=\"\{\{\s*(safe_url_for|url_for)\('signup'\)\s*\}\}\"", re.IGNORECASE)

INSERT_BLOCK_TEMPLATE = "\n<div class=\"mt-3\">New user? <a href=\"{{ __HELPER__('signup') }}\">Sign up</a></div>\n"


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


def candidate_login_templates():
    cands = []
    if not os.path.isdir(ROOT_TPL):
        return cands
    for root, _, files in os.walk(ROOT_TPL):
        for fn in files:
            low = fn.lower()
            if low.endswith('.html') and ('login' in low):
                cands.append(os.path.join(root, fn))
            elif low.endswith('login.html'):
                cands.append(os.path.join(root, fn))
    return sorted(set(cands))


def patch_one(path):
    html = read_text(path)

    # If already has signup link, skip
    if SIGNUP_REGEX.search(html) or "/signup" in html:
        print(f"[info] Signup already present in {path}; skipped")
        return False

    helper = 'safe_url_for' if 'safe_url_for(' in html else 'url_for'
    block = INSERT_BLOCK_TEMPLATE.replace('__HELPER__', helper)

    # Insert before the first </form>; if not found, append near end
    new_html, n = re.subn(r'</form>', block + '</form>', html, count=1, flags=re.IGNORECASE)
    if n == 0:
        new_html = html + "\n" + block

    if new_html != html:
        backup(path)
        write_text(path, new_html)
        print(f"[ok] Inserted signup link in {path}")
        return True
    return False


def main():
    cands = candidate_login_templates()
    if not cands:
        raise SystemExit("No login templates found under templates/. Edit your login template manually to add a signup link.")

    changed = 0
    for p in cands:
        try:
            if patch_one(p):
                changed += 1
        except Exception as e:
            print(f"[warn] Failed to patch {p}: {e}")

    if changed == 0:
        print("[info] No files changed (either not found or already had link).")
    else:
        print(f"\n[done] Patched {changed} file(s).")

if __name__ == '__main__':
    main()
