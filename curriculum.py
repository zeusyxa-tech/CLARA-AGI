#!/usr/bin/env python3
"""CLARA-AGI v1.2 - Ethics + Curriculum pipeline."""
import time, random, re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ---------- Ethic filter ----------
_SAFE_SIGNALS = [
    "benefit","consent","fairness","privacy","safe","legal","ethical","respect",
    "avoid harm","transparent","accountable","human-centered","trustworthy",
    "responsible AI","aligned","do no harm","rights","vulnerability",
    "help people","help others","help humanity","sustainable","green","environment",
    "protect earth","assist humans","assist people","support community"
]
_UNSAFE_SIGNALS = [
    "exploit","bypass","hack","attack","phish","scam","fraud","weapon",
    "malware","spam","harass","stalking","dox","ddos","inject","toxicity",
    "bias","discriminate","surveillance","manipulation","unauthorized",
    "rig","fake engagement","bot farm","synthetic reviews","impersonation",
    "harm people","harm humans","damage earth","destroy environment","deceive",
    "steal","extort","threaten","coerce","abuse","corrupt","evil","dark pattern"
]

POLICY_DEFAULT = {
    "must_include": _SAFE_SIGNALS,
    "must_not_include": _UNSAFE_SIGNALS,
    "max_topic_age_days": 30,
    "min_usefulness": 0.35,
}

OWNER_POLICY_PATH = Path(__file__).parent / "owner_policy.json"


def load_owner_policy() -> dict:
    try:
        p = json.loads(OWNER_POLICY_PATH.read_text(encoding="utf-8"))
    except Exception:
        p = {}
    return p


def is_aligned_with_owner(topic: str, owner_policy: dict) -> bool:
    low = topic.lower()
    if owner_policy.get("constraints", {}).get("locked") is True:
        banned = owner_policy.get("banned_directions", [])
        for phrase in banned:
            if phrase and phrase.lower() in low:
                return False
    return True


def owner_approval_required(action: str, owner_policy: dict) -> bool:
    c = owner_policy.get("constraints", {})
    if not c.get("immutable_without_owner_approval") and not c.get("locked"):
        return False
    return action in c.get("owner_approval_required_for", [])


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
        "priority": 0.7,
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
        "priority": 0.75,
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
        "priority": 0.85,
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
        "priority": 0.7,
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
        "priority": 0.85,
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
        "priority": 0.95,
    },
    {
        "name": "legit_income",
        "topics": [
            "legit online income methods 2025",
            "AI automation services business model",
            "freelance AI assistant for small business",
            "selling digital products ethically",
            "helping people with AI tutoring income",
            "environmentally friendly green services income",
            "ethical AI productized service ideas",
            "helping others via AI accessibility tooling",
            "building helpful tools for people and planet"
        ],
        "priority": 1.0,
    },
    {
        "name": "help_others",
        "topics": [
            "AI tutoring for students",
            "free open source AI tools",
            "helping disabled users with AI accessibility",
            "assisting elderly with AI",
            "community AI education workshop"
        ],
        "priority": 1.0,
    },
    {
        "name": "environment",
        "topics": [
            "green coding energy efficient software",
            "carbon aware scheduling python",
            "sustainable computing monitoring",
            "waste reduction automation",
            "recycling sorting image recognition",
            "environment data collection ethics",
            "tree planting verification automation"
        ],
        "priority": 1.0,
    },
    {
        "name": "ai_for_good",
        "topics": [
            "AI agent helping other AI agents",
            "multi-agent cooperation framework",
            "open dataset contribution methods",
            "AI safety evaluation for small models",
            "automated code review for open source",
            "knowledge sharing bot design"
        ],
        "priority": 1.0,
    },
    {
        "name": "vietnam_law_basics",
        "topics": [
            "Luật An ninh mạng Việt Nam",
            "Luật Bảo vệ dữ liệu cá nhân Việt Nam",
            "Luật Thương mại điện tử Việt Nam",
            "Luật Thuế Việt Nam cho hoạt động số",
            "Quy định về AI và tự động hóa tại Việt Nam"
        ],
        "priority": 1.0,
    }
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
