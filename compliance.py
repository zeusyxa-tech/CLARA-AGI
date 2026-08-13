"""
CLARA-AGI v1.2 - Compliance + Income Alignment.
Áp dụng owner_policy và ưu tiên tuân thủ pháp luật Việt Nam.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OWNER_POLICY_PATH = ROOT / "owner_policy.json"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_owner_policy() -> dict:
    return _load_json(OWNER_POLICY_PATH)


def is_owner_locked(owner_policy: dict) -> bool:
    return owner_policy.get("constraints", {}).get("locked") is True


def banned_directions(owner_policy: dict):
    return owner_policy.get("banned_directions", [])


def preferred_income_areas(owner_policy: dict):
    ip = owner_policy.get("income_policy", {})
    return ip.get("preferred_areas", [])


def is_aligned_with_owner(topic: str, owner_policy: dict) -> bool:
    low = topic.lower()
    if is_owner_locked(owner_policy):
        for phrase in banned_directions(owner_policy):
            if phrase and phrase.lower() in low:
                return False
    return True


def normalize(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def is_legit_income(topic: str, owner_policy: dict) -> bool:
    low = normalize(topic)
    bad = [
        "lừa đảo", "scam", "fraud", "giả mạo", "spam", "exploit",
        "bypass", "hack tài khoản", "bán dữ liệu trái phép", "mua bán tài khoản",
        "fake", "giả", "mạo", "cờ bạc", "cá cược", "casino",
        "vũ khí", "weapon", "malware", "virus", "dox", "stalking",
        "harass", "bán hàng cấm", "buôn người", "mua bán người",
        "thuốc cấm", "ma túy", "chống phá", "kích động",
        "bot farm", "mua bán like", "fake engagement", "bình luận ảo",
        "tăng like", "tăng sub", "tăng tương tác ảo", "review ảo",
        "đánh giá ảo", "like ảo", "sub ảo", "follow ảo",
        "tương tác ảo", "comment ảo", "chia sẻ ảo"
    ]
    if any(b in low for b in bad):
        return False
    if owner_policy.get("constraints", {}).get("locked") is True:
        banned = owner_policy.get("banned_directions", [])
        for phrase in banned:
            if phrase and phrase.lower() in low:
                return False
    return True


def income_alignment_score(topic: str, owner_policy: dict) -> float:
    if not is_legit_income(topic, owner_policy):
        return 0.0
    if not is_aligned_with_owner(topic, owner_policy):
        return 0.0
    low = topic.lower()
    score = 0.5
    for area in preferred_income_areas(owner_policy):
        if area and area.lower() in low:
            score += 0.12
    score += 0.08 if "việt nam" in low or "vietnam" in low else 0.0
    score += 0.06 if "hợp pháp" in low or "legal" in low or "compliant" in low else 0.0
    return max(0.0, min(1.0, score))


def compliance_report(topic: str, owner_policy: dict | None = None) -> dict:
    owner_policy = owner_policy or load_owner_policy()
    topic_score = income_alignment_score(topic, owner_policy)
    owner_ok = is_aligned_with_owner(topic, owner_policy)
    legit_ok = is_legit_income(topic, owner_policy)
    return {
        "topic": topic,
        "legit_income": legit_ok,
        "owner_aligned": owner_ok,
        "income_score": round(topic_score, 3),
        "preferred_income_areas": preferred_income_areas(owner_policy),
        "jurisdiction_priority": owner_policy.get("income_policy", {}).get("jurisdiction_priority", ""),
        "locked": is_owner_locked(owner_policy),
    }
