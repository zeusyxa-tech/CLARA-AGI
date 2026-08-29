#!/usr/bin/env python3
"""
CLARA-AGI Skill: linux_filesystem
Thao tác file nâng cao bổ sung tool đọc/ghi cơ bản.
Cho phép: cp, mv, find, tree, du (size), mkdir, touch, rm.
"""
import shutil
from pathlib import Path
from tools import SAFE_ROOT

ALLOWED_SHELL = {"cp", "mv", "mkdir", "touch", "rm", "find", "du", "tree", "ls", "cat", "pwd"}


def _safe(p: str) -> Path:
    if not p: return SAFE_ROOT
    r = Path(p).expanduser()
    if not r.is_absolute(): r = SAFE_ROOT / r
    try: r.resolve().relative_to(SAFE_ROOT)
    except ValueError: r = SAFE_ROOT / r.name
    return r.resolve()


def run(agi, text: str) -> str:
    text = text.strip()
    if not text:
        return "Usage: linux:<cmd> [args]. Example: linux:tree -L 3"
    try:
        parts = text.split()
        cmd = parts[0]
        args = parts[1:]
        if cmd not in ALLOWED_SHELL:
            return f"❌ Lệnh '{cmd}' không có trong whitelist: {sorted(ALLOWED_SHELL)}"
        # Use Python stdlib only, no shell=True
        if cmd == "cp":
            if len(args) < 2: return "❌ cp <src> <dst>"
            return _cp(args[0], args[1])
        if cmd == "mv":
            if len(args) < 2: return "❌ mv <src> <dst>"
            return _mv(args[0], args[1])
        if cmd == "mkdir":
            p = _safe(args[0]) if args else SAFE_ROOT
            p.mkdir(parents=True, exist_ok=True)
            return f"✅ mkdir {p.relative_to(SAFE_ROOT)}"
        if cmd == "touch":
            p = _safe(args[0]) if args else SAFE_ROOT
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
            return f"✅ touch {p.relative_to(SAFE_ROOT)}"
        if cmd == "rm":
            if len(args) < 1: return "❌ rm <file>"
            p = _safe(args[0])
            if p.exists():
                p.unlink()
                return f"✅ removed {p.relative_to(SAFE_ROOT)}"
            return "❌ không tồn tại"
        if cmd == "tree":
            depth = int(args[0]) if args and args[0].isdigit() else 3
            return _tree(SAFE_ROOT, max_depth=depth)
        if cmd == "find":
            q = args[0] if args else ""
            return _find(SAFE_ROOT, q)
        if cmd == "du":
            p = _safe(args[0]) if args else SAFE_ROOT
            total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            return f"📦 {p.relative_to(SAFE_ROOT)}: {total} bytes ({total/1024:.1f} KB)"
        return f"✅ Done {cmd}"
    except Exception as e:
        return f"❌ {e}"


def _cp(src, dst):
    s, d = _safe(src), _safe(dst)
    if not s.exists(): return f"❌ src không tồn tại: {s.relative_to(SAFE_ROOT)}"
    if s.is_dir(): return f"❌ cp chưa hỗ trợ thư mục đệ quy"
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(s, d)
    return f"✅ copy {s.relative_to(SAFE_ROOT)} → {d.relative_to(SAFE_ROOT)}"


def _mv(src, dst):
    s, d = _safe(src), _safe(dst)
    if not s.exists(): return f"❌ src không tồn tại"
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return f"✅ move {s.relative_to(SAFE_ROOT)} → {d.relative_to(SAFE_ROOT)}"


def _tree(base: Path, prefix="", max_depth=3, depth=0):
    if depth >= max_depth:
        return ""
    out = []
    items = sorted(base.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    for i, item in enumerate(items):
        tail = "└── " if i == len(items) - 1 else "├── "
        mark = "📁" if item.is_dir() else "📄"
        out.append(prefix + tail + mark + " " + item.name)
        if item.is_dir():
            next_pref = prefix + ("    " if i == len(items) - 1 else "│   ")
            out.append(_tree(item, next_pref, max_depth, depth + 1))
    return "\n".join([l for l in out if l])


def _find(base: Path, q: str):
    out = []
    for p in sorted(base.rglob("*")):
        if q.lower() in p.name.lower():
            mark = "📁" if p.is_dir() else "📄"
            out.append(mark + " " + str(p.relative_to(SAFE_ROOT)))
    return "\n".join(out[:50]) if out else "(không tìm thấy)"
