#!/usr/bin/env python3
"""
CLARA-AGI Skill: income_roadmap
Track and advance legit income paths aligned with owner_policy.
Allowed focus areas:
- crypto (trading, research, bounties)
- stock-market analysis, paper/live trading where legal
- online work, freelancing, microtask/bounties
- community tools and services
"""
import json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROADMAP_FILE = ROOT / "workspace" / "income_roadmap.json"
DEFAULT = {
    "jurisdiction": "Việt Nam",
    "locked": True,
    "current_focus": [
        "freelance AI services for small business",
        "community AI tooling and education",
        "environmentally friendly automation",
        "bounties and open-source rewards"
    ],
    "execution_plans": [],
    "completed_milestones": [],
    "next_actions": [],
    "constraints": [
        "Tuân thủ pháp luật Việt Nam",
        "Không vi phạm thuế, kinh doanh, dữ liệu cá nhân, AI",
        "Ưu tiên giúp người, cộng đồng, môi trường"
    ],
    "last_updated": None,
}


def _load():
    if ROADMAP_FILE.exists():
        try:
            return json.loads(ROADMAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT)


def _save(state):
    ROADMAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = __import__("datetime").datetime.now().isoformat()
    ROADMAP_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        state = _load()
        return json.dumps(state, ensure_ascii=False, indent=2)
    sub = text.split("|")[0].strip().lower()
    arg = text.split("|", 1)[1].strip()
    try:
        state = _load()
        if sub == "status":
            return json.dumps(state, ensure_ascii=False, indent=2)
        if sub == "add_focus":
            if arg and arg not in state["current_focus"]:
                state["current_focus"].append(arg)
                _save(state)
                agi.mem.remember_episode("income_roadmap", f"add_focus: {arg}", importance=0.7, emotion=0.2)
                return f"✅ Added focus: {arg}"
            return "Focus already exists or empty."
        if sub == "add_action":
            if not arg:
                return "Dùng: income_roadmap:add_action|<mô tả hành động>"
            state["next_actions"].append(arg)
            _save(state)
            return f"✅ Added next action: {arg}"
        if sub == "complete_action":
            if arg in state.get("next_actions", []):
                state["next_actions"].remove(arg)
            state["completed_milestones"].append(arg)
            _save(state)
            return f"✅ Completed: {arg}"
        if sub == "set_execution_plan":
            if not arg:
                return "Dùng: income_roadmap:set_execution_plan|<plan json or text>"
            state["execution_plans"].append(arg)
            _save(state)
            return f"✅ Saved execution plan ({len(arg)} chars)"
        if sub == "clear":
            _save(dict(DEFAULT))
            return "Cleared income_roadmap."
        return "Usage: income_roadmap:<status|add_focus|add_action|complete_action|set_execution_plan|clear>|<args>"
    except Exception as e:
        return f"❌ {e}"
