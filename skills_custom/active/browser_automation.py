#!/usr/bin/env python3
"""
CLARA-AGI Skill: browser_automation
Structured browser handoff notes for desktop/browser-use integrations.
This skill prepares browser action plans Hermes/CLARA can execute via tool.
"""
import json


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: browser:<subcmd>|<payload>\n"
                "  plan:<goal>                 generate browser action plan\n"
                "  verify:<url>                quick page verification checklist\n"
                "  snapshot:<selector hint>    target snapshot strategy\n"
                "  form:<fields>               form-fill plan")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub.startswith("plan"):
            plan = {
                "goal": payload,
                "steps": ["navigate", "snapshot", "act", "verify"],
                "warnings": ["avoid CAPTCHA", "respect robots"],
            }
            agi.mem.remember_episode("browser_plan", json.dumps(plan), importance=0.5, emotion=0.1)
            return json.dumps(plan, ensure_ascii=False, indent=2)
        if sub.startswith("verify"):
            return json.dumps({
                "url": payload,
                "checks": ["http_200", "title_present", "no_console_errors", "no_broken_images"],
                "status": "pending",
            }, ensure_ascii=False, indent=2)
        if sub.startswith("form"):
            fields = [f.strip() for f in payload.split(",") if f.strip()]
            return json.dumps({
                "fields": fields,
                "order": "top_to_bottom",
                "submit": "after_last_field",
            }, ensure_ascii=False, indent=2)
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
