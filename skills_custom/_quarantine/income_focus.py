#!/usr/bin/env python3
"""
CLARA-AGI Skill: income_focus
Choose and execute focused income paths with compliance enforcement.
Paths:
- freelance AI services
- community tooling/education
- open-source bounties
- environmental automation
"""
import json, re
from pathlib import Path

try:
    from compliance import compliance_report, load_owner_policy
    _HAS_COMPLIANCE = True
except Exception:
    _HAS_COMPLIANCE = False

ROOT = Path(__file__).resolve().parents[2]
FOCUS_FILE = ROOT / "workspace" / "income_focus.json"
DEFAULT = {
    "current_path": None,
    "approved_paths": [
        "freelance_ai_services",
        "community_ai_education",
        "open_source_bounties",
        "environmental_automation",
        "ai_accessibility_tools"
    ],
    "blocked_paths": [],
    "weekly_targets": [],
    "execution_log": [],
    "last_updated": None,
}


def _load():
    if FOCUS_FILE.exists():
        try:
            return json.loads(FOCUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT)


def _save(state):
    FOCUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = __import__("datetime").datetime.now().isoformat()
    FOCUS_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _compliance_ok(text):
    if not _HAS_COMPLIANCE:
        return True
    try:
        report = compliance_report(text, load_owner_policy())
        return report["legit_income"] and report["owner_aligned"] and report["income_score"] >= 0.35
    except Exception:
        return True


def _validate_path(path):
    low = path.lower()
    bad = [
        "cờ bạc", "cá cược", "casino", "trading binary", "binance scam",
        "bot farm", "mua bán like", "fake engagement", "review ảo",
        "lừa đảo", "scam", "exploit", "hack", "phishing", "malware",
        "vũ khí", "ma túy", "chống phá", "kích động"
    ]
    if any(b in low for b in bad):
        return False
    if _HAS_COMPLIANCE:
        return _compliance_ok(path)
    return True


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        state = _load()
        return json.dumps(state, ensure_ascii=False, indent=2)
    sub = text.split("|")[0].strip().lower()
    arg = text.split("|", 1)[1].strip()
    try:
        if sub == "set_path":
            if not arg:
                return "Dùng: income_focus:set_path|<path>"
            if not _validate_path(arg):
                return f"❌ Path blocked by compliance policy: {arg}"
            state = _load()
            if arg not in state["approved_paths"]:
                state["approved_paths"].append(arg)
            state["current_path"] = arg
            _save(state)
            agi.mem.remember_episode("income_focus", f"set_path: {arg}", importance=0.8, emotion=0.3)
            return f"✅ Income focus set: {arg}"
        if sub == "add_target":
            if not arg:
                return "Dùng: income_focus:add_target|<mục tiêu>"
            state = _load()
            state["weekly_targets"].append(arg)
            _save(state)
            return f"✅ Added target: {arg}"
        if sub == "log":
            if not arg:
                return "Dùng: income_focus:log|<ghi chú hành động>"
            state = _load()
            state["execution_log"].append({"ts": __import__("datetime").datetime.now().isoformat(), "note": arg})
            if len(state["execution_log"]) > 200:
                state["execution_log"] = state["execution_log"][-200:]
            _save(state)
            return f"✅ Logged: {arg}"
        if sub == "block_path":
            if not arg:
                return "Dùng: income_focus:block_path|<path>"
            state = _load()
            state["blocked_paths"].append(arg)
            if state.get("current_path") == arg:
                state["current_path"] = None
            _save(state)
            return f"🚫 Blocked path: {arg}"
        if sub == "status":
            state = _load()
            return json.dumps(state, ensure_ascii=False, indent=2)
        return "Usage: income_focus:<set_path|add_target|log|block_path|status>|<args>"
    except Exception as e:
        return f"❌ {e}"
