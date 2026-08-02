#!/usr/bin/env python3
"""CLARA-AGI Skill: ops_sync"""
from skills_custom import SKILLS_MANIFEST as CATALOG


def _collect_tools(agi):
    try:
        from tools import TOOLS
        return TOOLS
    except Exception:
        return {}


def _load_missing(agi):
    try:
        from self_improve import load_custom_skills
        return load_custom_skills(agi)
    except Exception as e:
        return [f"err:{e}"]


def _report_status(agi) -> str:
    try:
        from self_improve import list_active, list_pending
        loaded = [s["file"] for s in list_active()]
        pending = [s["file"] for s in list_pending()]
    except Exception:
        loaded = []
        pending = []
    lines = [
        "🧰 CLARA Skills Catalog",
        f"   Registry : {len(CATALOG)} skills",
        f"   Active .py: {len(loaded)}",
        f"   Pending   : {len(pending)}",
        "",
    ]
    for group in ("active", "docs"):
        items = [(n, m) for n, m in CATALOG.items() if m["kind"] == group]
        if items:
            label = "active" if group == "active" else "docs"
            lines.append(f"▶ {label} ({len(items)})")
            for name, meta in items[:14]:
                mark = "✓" if name in [p.replace(".py","") for p in loaded] else " "
                lines.append(f"  {mark} {name}: {meta['desc'][:50]}")
    return "\n".join(lines)


def run(agi, text: str) -> str:
    text = text.strip()
    if not text:
        return _report_status(agi)
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if cmd in ("status", "list", "trạng thái"):
        return _report_status(agi)
    if cmd == "load":
        missing = _load_missing(agi)
        if missing:
            return f"✅ Đã nạp: {', '.join(missing)}"
        return "ℹ️ Không có skill mới."
    return f"ops_sync: '{cmd}' không hợp lệ. Gõ 'ops_sync' để xem status."
