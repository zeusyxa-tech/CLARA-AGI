#!/usr/bin/env python3
"""
CLARA-AGI Skill: income_portfolio
Track income attempts: projects, proposals, platforms, outcomes.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO_FILE = ROOT / "workspace" / "income_portfolio.json"
DEFAULT = {
    "platforms": [],
    "projects": [],
    "proposals": [],
    "bounties": [],
    "outcomes": [],
    "next_reviews": [],
    "last_updated": None,
}


def _load():
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT)


def _save(state):
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = __import__("datetime").datetime.now().isoformat()
    PORTFOLIO_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _append(state, key, item):
    state.setdefault(key, [])
    item["ts"] = __import__("datetime").datetime.now().isoformat()
    state[key].append(item)
    if len(state[key]) > 200:
        state[key] = state[key][-200:]
    _save(state)
    return item


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        state = _load()
        return json.dumps(state, ensure_ascii=False, indent=2)
    sub = text.split("|")[0].strip().lower()
    arg = text.split("|", 1)[1].strip()
    try:
        state = _load()
        if sub == "add_platform":
            if not arg:
                return "Dùng: income_portfolio:add_platform|<name>|<url>|<note>"
            parts = arg.split("|")
            name = parts[0].strip()
            url = parts[1].strip() if len(parts) > 1 else ""
            note = parts[2].strip() if len(parts) > 2 else ""
            item = {"name": name, "url": url, "note": note, "status": "active"}
            _append(state, "platforms", item)
            agi.mem.remember_episode("income_portfolio", f"add_platform: {name}", importance=0.6, emotion=0.1)
            return f"✅ Added platform: {name}"
        if sub == "add_project":
            if not arg:
                return "Dùng: income_portfolio:add_project|<title>|<client>|<status>"
            parts = arg.split("|")
            title = parts[0].strip()
            client = parts[1].strip() if len(parts) > 1 else ""
            status = parts[2].strip() if len(parts) > 2 else "new"
            item = {"title": title, "client": client, "status": status}
            _append(state, "projects", item)
            return f"✅ Added project: {title}"
        if sub == "add_proposal":
            if not arg:
                return "Dùng: income_portfolio:add_proposal|<title>|<client>|<url>|<status>"
            parts = arg.split("|")
            title = parts[0].strip()
            client = parts[1].strip() if len(parts) > 1 else ""
            url = parts[2].strip() if len(parts) > 2 else ""
            status = parts[3].strip() if len(parts) > 3 else "sent"
            item = {"title": title, "client": client, "url": url, "status": status}
            _append(state, "proposals", item)
            return f"✅ Added proposal: {title}"
        if sub == "add_bounty":
            if not arg:
                return "Dùng: income_portfolio:add_bounty|<title>|<platform>|<reward>|<status>"
            parts = arg.split("|")
            title = parts[0].strip()
            platform = parts[1].strip() if len(parts) > 1 else ""
            reward = parts[2].strip() if len(parts) > 2 else ""
            status = parts[3].strip() if len(parts) > 3 else "new"
            item = {"title": title, "platform": platform, "reward": reward, "status": status}
            _append(state, "bounties", item)
            return f"✅ Added bounty: {title}"
        if sub == "status":
            state = _load()
            return json.dumps(state, ensure_ascii=False, indent=2)
        if sub == "export":
            state = _load()
            return json.dumps(state, ensure_ascii=False, indent=2)
        return "Usage: income_portfolio:<add_platform|add_project|add_proposal|add_bounty|status|export>|<args>"
    except Exception as e:
        return f"❌ {e}"
