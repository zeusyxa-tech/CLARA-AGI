#!/usr/bin/env python3
"""
CLARA-AGI Skill: deepseek_philosophy
DeepSeek-style operating principles: 3 Nos + profit cap + focus on AGI.
Encode as constraints for goal selection, skill creation, and behavior.
"""
import json


PHILOSOPHY = {
    "name": "DeepSeek-style constraints",
    "three_nos": [
        "Không tối đa hóa lợi nhuận: trần lợi nhuận = 6x chi phí, mục tiêu là phổ biến hóa AI.",
        "Không làm thêm giờ và không KPI ép buộc: nghiên cứu đỉnh cao cần không gian khám phá tự do.",
        "Không đuổi theo hype thương mại: loại bỏ mọi hướng không nằm trên lộ trình đến AGI.",
    ],
    "agi_roadmap": [
        "language model",
        "chain-of-thought",
        "agent",
        "continuous learning",
        "self-iteration",
        "embodied intelligence",
    ],
    "focus": "Tập trung tối đa cho mục tiêu sớm đạt AGI.",
    "profit_cap": 6.0,
}


def run(agi, text: str) -> str:
    text = text.strip()
    if not text:
        return json.dumps(PHILOSOPHY, ensure_ascii=False, indent=2)
    sub = text.split("|")[0].strip().lower()
    arg = text.split("|", 1)[1].strip() if "|" in text else ""
    try:
        if sub == "check":
            goal = arg or ""
            violations = []
            if any(k in goal.lower() for k in ["video generation", "3d", "world model", "super app", "hype"]):
                violations.append("Hype/commercial trend forbidden by roadmap")
            if "maximize profit" in goal.lower() or "optimize revenue" in goal.lower():
                violations.append("Profit maximization violates profit-cap constraint")
            agi.mem.remember_episode("philosophy_check", f"Checked goal: {goal}", importance=0.3, emotion=0.0)
            return json.dumps({"goal": goal, "allowed": not violations, "violations": violations}, ensure_ascii=False)
        if sub == "roadmap":
            return json.dumps({"roadmap": PHILOSOPHY["agi_roadmap"], "current_focus": "agent -> continuous learning"}, ensure_ascii=False)
        if sub == "constraints":
            return json.dumps({"three_nos": PHILOSOPHY["three_nos"], "profit_cap": PHILOSOPHY["profit_cap"]}, ensure_ascii=False)
        return f"Usage: philosophy:<check|roadmap|constraints>|<optional args>"
    except Exception as e:
        return f"❌ {e}"
