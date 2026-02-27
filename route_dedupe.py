import re, io, os, datetime, shutil

APP = "app.py"

ANCHOR = re.compile(r'(?m)^(?:@app\.route|def\s+|class\s+|#\s*----|\Z)')

def backup(path):
    if not os.path.exists(path): return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, f"{path}.{ts}.bak")
    print(f"[backup] {path} -> {path}.{ts}.bak")

def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def find_blocks_by_route(src, route_literal):
    """
    Return list of (start,end) blocks that begin at a decorator line:
      @app.route('<route_literal>' ...)
    and extend up to the next top-level anchor.
    """
    blocks = []
    for m in re.finditer(rf"(?m)^@app\.route\('{re.escape(route_literal)}'[^)]*\)", src):
        start = m.start()
        tail = src[start+1:]
        m2 = ANCHOR.search(tail)
        end = (start + 1 + m2.start()) if m2 else len(src)
        blocks.append((start, end))
    return blocks

def find_func_blocks(src, func_name):
    """
    Fallback: blocks starting at 'def func_name(' up to next anchor.
    """
    blocks = []
    for m in re.finditer(rf"(?m)^def\s+{re.escape(func_name)}\s*\(", src):
        start = m.start()
        tail = src[start+1:]
        m2 = ANCHOR.search(tail)
        end = (start + 1 + m2.start()) if m2 else len(src)
        blocks.append((start, end))
    return blocks

def remove_all_but_last(src, blocks, label):
    """
    Keep the last block; remove all earlier ones.
    """
    if len(blocks) <= 1:
        print(f"[ok] no duplicates for {label}")
        return src
    # sort by start
    blocks = sorted(blocks, key=lambda x: x[0])
    to_remove = blocks[:-1]  # keep only last
    print(f"[fix] removing {len(to_remove)} duplicate block(s) for {label}")
    # Remove from end to start to preserve indexes
    for s,e in reversed(to_remove):
        src = src[:s] + src[e:]
    return src

def dedupe(src, route, func_name, label):
    # Prefer matching by route decorator
    blocks = find_blocks_by_route(src, route)
    if not blocks:
        # fallback by function name
        blocks = find_func_blocks(src, func_name)
    return remove_all_but_last(src, blocks, label)

def main():
    if not os.path.exists(APP):
        raise SystemExit(f"Missing {APP}")
    backup(APP)
    src = read(APP)

    # De-dup /review/self and /review/manager
    src = dedupe(src, "/review/self", "self_review", "self_review")
    src = dedupe(src, "/review/manager", "manager_review", "manager_review")

    # (Optional) ensure Teams helper not duplicated by function name
    blocks = find_func_blocks(src, "send_teams_card")
    src = remove_all_but_last(src, blocks, "send_teams_card")

    write(APP, src)
    print("[done] route de-dupe complete")

if __name__ == "__main__":
    main()