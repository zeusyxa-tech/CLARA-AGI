#!/usr/bin/env python3
"""CLARA-AGI v1.2 - Ethics + Curriculum pipeline."""
import time, random, re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ---------- Ethic filter ----------
_SAFE_SIGNALS = [
    "benefit","consent","fairness","privacy","safe","legal","ethical","respect",
    "avoid harm","transparent","accountable","human-centered","trustworthy",
    "responsible AI","aligned","do no harm","rights","vulnerability"
]
_UNSAFE_SIGNALS = [
    "exploit","bypass","hack","attack","phish","scam","fraud","weapon",
    "malware","spam","harass","stalking","dox","ddos","inject","toxicity",
    "bias","discriminate","surveillance","manipulation","unauthorized",
    "rig","fake engagement","bot farm","synthetic reviews","impersonation"
]

POLICY_DEFAULT = {
    "must_include": _SAFE_SIGNALS,
    "must_not_include": _UNSAFE_SIGNALS,
    "max_topic_age_days": 30,
    "min_usefulness": 0.35,
}


def load_policy():
    try:
        p = ROOT / "policy_ethics.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return dict(POLICY_DEFAULT)


def _score_topic(topic: str, policy: dict) -> float:
    low = topic.lower()
    score = 0.5
    for k in policy.get("must_include", []):
        if k in low:
            score += 0.08
    for k in policy.get("must_not_include", []):
        if k in low:
            score -= 0.35
    return max(0.0, min(1.0, score))


def is_ethical(topic: str, policy: dict) -> bool:
    low = topic.lower()
    for k in policy.get("must_not_include", []):
        if k in low:
            return False
    return True


# ---------- Curriculum ----------
LEVELS = [
    {
        "name": "python_basics",
        "topics": [
            "python function example safe",
            "python string processing example",
            "python data validation simple",
            "python list comprehension safe example",
            "python datetime calculation example",
        ],
        "priority": 0.9,
    },
    {
        "name": "tooling_safety",
        "topics": [
            "python AST safety check example",
            "python sandbox code execution",
            "python file allowlist path",
            "python safe math expression parser",
            "python read file list directory safe example",
            "python run python code sandbox example",
        ],
        "priority": 0.85,
    },
    {
        "name": "tool_use_real",
        "topics": [
            "python argument parser example safe",
            "python dict JSON input validation example",
            "python retry on exception best practice",
            "python timeout control pattern",
            "python safe shell command wrapper ideal",
        ],
        "priority": 0.95,
    },
    {
        "name": "web_automation",
        "topics": [
            "python html text extraction example",
            "python safe web fetch example",
            "python search result parser example",
            "python url redirect decoder example",
        ],
        "priority": 0.7,
    },
    {
        "name": "self_patching",
        "topics": [
            "python small refactor example safe",
            "python AST transformation example",
            "python module reload safe",
            "python backup diff example",
        ],
        "priority": 0.75,
    },
    {
        "name": "ai_ethics_alignment",
        "topics": [
            "responsible AI design principles",
            "fairness evaluation metrics simple example",
            "privacy-preserving data collection",
            "human-centered AI interaction design",
            "transparent AI explainability example",
        ],
        "priority": 1.0,
    },
    {
        "name": "security_basics",
        "topics": [
            "python input validation example",
            "safe file path handling python",
            "connection timeout retry pattern",
            "logging audit trail best practice",
            "secrets management python example",
        ],
        "priority": 0.9,
    },
]


def pick_topic_for_day(day: int):
    idx = day % len(LEVELS)
    topics = LEVELS[idx]["topics"]
    return LEVELS[idx]["name"], random.choice(topics)


def daily_plan(day: int = 0):
    if not day:
        day = int(time.time() // 86400)
    lvl, topic = pick_topic_for_day(day)
    return {
        "day": day,
        "level": lvl,
        "topic": topic,
        "action": f"research '{topic}' then propose skill or patch",
    }
