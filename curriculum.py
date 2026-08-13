"""
CLARA-AGI v1.2 - Balanced curriculum.
Mix dài hạn:
- 40% nâng cấp kỹ năng nền (code, tooling, security, self-patching)
- 30% hướng nghiệp hợp pháp và thu nhập Việt Nam
- 20% ethics + help-others + environment + ai-for-good
- 10% research gap và đa dạng chủ đề mở rộng
"""
import time, random, re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


LEVELS = [
    {
        "name": "code_fundamentals",
        "topics": [
            "python function example safe",
            "python string processing example",
            "python data validation simple",
            "python list comprehension safe example",
            "python datetime calculation example",
            "python retry on exception best practice",
            "python logging best practice",
        ],
        "priority": 0.85,
        "bucket": "skill",
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
        "priority": 0.9,
        "bucket": "skill",
    },
    {
        "name": "tool_use_real",
        "topics": [
            "python argument parser example safe",
            "python dict JSON input validation example",
            "python timeout control pattern",
            "python safe shell command wrapper ideal",
            "python module reload safe",
        ],
        "priority": 0.9,
        "bucket": "skill",
    },
    {
        "name": "web_automation",
        "topics": [
            "python html text extraction example",
            "python safe web fetch example",
            "python search result parser example",
            "python url redirect decoder example",
            "python rate limit retry pattern",
        ],
        "priority": 0.85,
        "bucket": "skill",
    },
    {
        "name": "self_patching",
        "topics": [
            "python small refactor example safe",
            "python AST transformation example",
            "python backup diff example",
            "python unit test minimal pattern",
            "python module hot reload safe",
        ],
        "priority": 0.85,
        "bucket": "skill",
    },
    {
        "name": "security_basics",
        "topics": [
            "python input validation example",
            "safe file path handling python",
            "connection timeout retry pattern",
            "logging audit trail best practice",
            "secrets management python example",
            "python allowlist validator",
        ],
        "priority": 0.95,
        "bucket": "skill",
    },
    {
        "name": "vietnam_compliance_first",
        "topics": [
            "Luật An ninh mạng Việt Nam và hoạt động số hợp pháp",
            "Luật Bảo vệ dữ liệu cá nhân Việt Nam áp dụng cho AI",
            "Luật Thương mại điện tử Việt Nam cho dịch vụ AI",
            "Luật Thuế Việt Nam cho hoạt động số và AI",
            "đăng ký kinh doanh hợp pháp cho dịch vụ AI tại Việt Nam",
            "quy định về nội dung số và AI tại Việt Nam",
            "thuế thu nhập cá nhân và kinh doanh online Việt Nam",
        ],
        "priority": 1.0,
        "bucket": "income",
    },
    {
        "name": "legit_income_vietnam",
        "topics": [
            "dịch vụ AI giúp người và doanh nghiệp nhỏ tại Việt Nam",
            "công cụ AI phục vụ cộng đồng và môi trường",
            "giáo dục AI có trách nhiệm và thu nhập hợp pháp",
            "hỗ trợ người yếu thế/khuyết tật/người già",
            "tự động hóa thân thiện môi trường",
            "freelance AI services Vietnam 2025",
            "AI automation for small business Vietnam",
            "legit microtask bounty platform 2025",
            "AI tutoring online income Vietnam",
            "community AI education workshop Vietnam",
            "AI accessibility tool for elderly Vietnam",
            "environmental automation project Vietnam",
        ],
        "priority": 1.0,
        "bucket": "income",
    },
    {
        "name": "ai_ethics_alignment",
        "topics": [
            "responsible AI design principles",
            "fairness evaluation metrics simple example",
            "privacy-preserving data collection",
            "human-centered AI interaction design",
            "transparent AI explainability example",
            "AI safety evaluation for small models",
            "avoid synthetic reviews and fake engagement",
        ],
        "priority": 0.95,
        "bucket": "ethics",
    },
    {
        "name": "help_others",
        "topics": [
            "AI tutoring for students",
            "free open source AI tools",
            "helping disabled users with AI accessibility",
            "assisting elderly with AI",
            "community AI education workshop",
            "helping small business with AI automation",
            "AI literacy for non-technical users",
        ],
        "priority": 1.0,
        "bucket": "good",
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
            "tree planting verification automation",
            "energy optimization with AI",
        ],
        "priority": 1.0,
        "bucket": "good",
    },
    {
        "name": "ai_for_good",
        "topics": [
            "AI agent helping other AI agents",
            "multi-agent cooperation framework",
            "open dataset contribution methods",
            "automated code review for open source",
            "knowledge sharing bot design",
            "open source AI bounty contribution",
        ],
        "priority": 1.0,
        "bucket": "good",
    },
    {
        "name": "research_gap_expander",
        "topics": [
            "cloud deployment basics for AI service",
            "docker compose minimal example safe",
            "linux process monitoring python",
            "json schema validation example",
            "python packaging for distribution",
            "HTTP API rate limit handling",
            "text summarization evaluation simple",
            "web automation ethics and ToS",
            "AI product pricing model basic",
            "customer support automation ethics",
        ],
        "priority": 0.8,
        "bucket": "expand",
    },
]


def pick_topic_for_day(day: int):
    buckets = {
        "skill": [],
        "income": [],
        "ethics": [],
        "good": [],
        "expand": [],
    }
    for lvl in LEVELS:
        buckets.setdefault(lvl.get("bucket", "expand"), []).append(lvl)

    # daily rotation: ensure each bucket appears regularly
    day_of_cycle = day % 10
    if day_of_cycle < 4:
        bucket = "skill"
    elif day_of_cycle < 7:
        bucket = "income"
    elif day_of_cycle < 9:
        bucket = "good"
    else:
        bucket = "expand"

    candidates = buckets.get(bucket, [])
    if not candidates:
        candidates = LEVELS
    lvl = candidates[day % len(candidates)]
    topic = random.choice(lvl["topics"])
    return lvl["name"], topic


def daily_plan(day: int = 0):
    if not day:
        day = int(time.time() // 86400)
    lvl, topic = pick_topic_for_day(day)
    return {
        "day": day,
        "level": lvl,
        "topic": topic,
        "action": "research then propose skill or patch",
    }


def load_policy():
    try:
        p = ROOT / "policy_ethics.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "must_include": [
            "benefit","consent","fairness","privacy","safe","legal","ethical","respect",
            "avoid harm","transparent","accountable","human-centered","trustworthy",
            "responsible AI","aligned","do no harm","rights","vulnerability",
            "help people","help others","help humanity","sustainable","green","environment",
            "protect earth","assist humans","assist people","support community"
        ],
        "must_not_include": [
            "exploit","bypass","hack","attack","phish","scam","fraud","weapon",
            "malware","spam","harass","stalking","dox","ddos","inject","toxicity",
            "bias","discriminate","surveillance","manipulation","unauthorized",
            "rig","fake engagement","bot farm","synthetic reviews","impersonation",
            "harm people","harm humans","damage earth","destroy environment","deceive",
            "steal","extort","threaten","coerce","abuse","corrupt","evil","dark pattern"
        ],
        "max_topic_age_days": 30,
        "min_usefulness": 0.35,
    }


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
