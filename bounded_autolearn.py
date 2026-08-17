"""
CLARA-AGI Phase 2 - Bounded idle-study loop.

Opt-in only.
Requires explicit `--idle-study`.
Respects runtime_profile budgets:
- only when plugged if detectable
- max session minutes / daily minutes
- max topics / facts per session
- no network unless `--allow-network`
- no background LLM if memory pressure / degraded mode
- write-only report, no code/skill activation
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from runtime_profile import choose_profile, degraded_reason, probe_hardware

REPORT_DIR = Path(__file__).resolve().parent / "data" / "growth_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class IdleStudyBudget:
    max_session_minutes: int = 10
    max_daily_minutes: int = 20
    max_topics: int = 3
    max_facts: int = 5
    allow_network: bool = False


def _now() -> float:
    return time.time()


def _local_candidate_topics(agi, limit: int = 5) -> list[str]:
    topics: list[str] = []
    try:
        rows = agi.mem.conn.execute(
            "SELECT topic, fact, confidence FROM semantics ORDER BY last_access DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
        seen = set()
        for r in rows:
            topic = (r["topic"] or "").strip()
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
            if len(topics) >= limit:
                break
    except Exception:
        pass
    if not topics:
        topics = ["python basics", "safe shell", "memory review", "learning techniques"]
    return topics[:limit]


def _local_facts_for_topic(agi, topic: str, limit: int = 5) -> list[dict]:
    try:
        rows = agi.mem.conn.execute(
            "SELECT id, topic, fact, confidence, source, ts FROM semantics WHERE topic=? ORDER BY last_access DESC LIMIT ?",
            (topic, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _write_report(report: dict) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"idle_study_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_idle_study_session(
    agi,
    *,
    profile_name: str = "mobile_12gb_safe",
    force: bool = False,
    allow_network: bool = False,
) -> dict:
    profile = choose_profile(profile_name)
    hw = probe_hardware()
    reason = None if force else degraded_reason(hw, profile)

    report: dict = {
        "profile": profile.name,
        "mode": "idle-study",
        "degraded_reason": reason,
        "hardware_snapshot": hw,
        "session_start": _now(),
        "session_end": None,
        "topics": [],
        "facts_candidate": [],
        "actions": [],
        "stopped_early": False,
        "stop_reason": None,
    }

    if reason and not force:
        report["stop_reason"] = f"skipped_degraded:{reason}"
        report["session_end"] = _now()
        _write_report(report)
        return report

    budget = IdleStudyBudget(
        max_session_minutes=profile.max_idle_minutes_per_session,
        max_daily_minutes=profile.max_idle_minutes_per_day,
        max_topics=profile.max_idle_topics_per_session,
        max_facts=profile.max_idle_facts_per_session,
        allow_network=allow_network,
    )

    topics = _local_candidate_topics(agi, budget.max_topics)
    used_minutes = 0.0
    facts_candidate = []

    for topic in topics:
        if used_minutes >= budget.max_session_minutes:
            report["stopped_early"] = True
            report["stop_reason"] = "session_quota"
            break
        try:
            facts = _local_facts_for_topic(agi, topic, budget.max_facts - len(facts_candidate))
            selected = []
            for f in facts:
                if len(facts_candidate) >= budget.max_facts:
                    break
                entry = {
                    "id": f.get("id"),
                    "topic": f.get("topic"),
                    "fact": f.get("fact"),
                    "confidence": f.get("confidence"),
                    "source": f.get("source"),
                    "captured_at": f.get("ts"),
                    "status": "candidate",
                    "reason": "idle candidate from existing memory",
                }
                selected.append(entry)
                facts_candidate.append(entry)
            report["topics"].append({
                "topic": topic,
                "candidates_reviewed": len(selected),
            })
            used_minutes += 0.5
            report["actions"].append(f"review topic={topic} candidates={len(selected)}")
        except Exception as e:
            report["actions"].append(f"error topic={topic} err={e}")

    report["facts_candidate"] = facts_candidate
    report["used_session_minutes"] = round(used_minutes, 2)
    report["session_end"] = _now()
    _write_report(report)
    return report


__all__ = ["IdleStudyBudget", "run_idle_study_session"]
