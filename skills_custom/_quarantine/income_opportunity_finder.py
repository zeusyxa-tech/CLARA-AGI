#!/usr/bin/env python3
"""
CLARA-AGI Skill: income_opportunity_finder
Find legit income opportunities aligned with owner_policy.
Allowed categories:
- freelance AI services
- open-source bounties/rewards
- microtasks/crowdsourcing
- community tooling and education
- environmental automation projects
"""
import json, re
from pathlib import Path

try:
    from web_tools import web_search
    _HAS_WEB = True
except Exception:
    _HAS_WEB = False

try:
    from compliance import compliance_report, load_owner_policy
    _HAS_COMPLIANCE = True
except Exception:
    _HAS_COMPLIANCE = False

ROOT = Path(__file__).resolve().parents[2]
LEADS_FILE = ROOT / "workspace" / "income_leads.json"


def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso():
    return __import__("datetime").datetime.now().isoformat()


def _append_lead(item):
    leads = _load_json(LEADS_FILE, {"leads": []})
    item["ts"] = _now_iso()
    item["status"] = item.get("status") or "new"
    leads["leads"].append(item)
    if len(leads["leads"]) > 200:
        leads["leads"] = leads["leads"][-200:]
    _save_json(LEADS_FILE, leads)
    return item


def _list_leads(status=None, limit=20):
    leads = _load_json(LEADS_FILE, {"leads": []})
    items = leads.get("leads", [])
    if status:
        items = [x for x in items if x.get("status") == status]
    return items[-limit:]


def _update_lead_status(url, status):
    leads = _load_json(LEADS_FILE, {"leads": []})
    for item in leads.get("leads", []):
        if item.get("url") == url:
            item["status"] = status
            item["updated_at"] = _now_iso()
            break
    _save_json(LEADS_FILE, leads)


def _default_queries():
    return [
        "freelance AI services Vietnam 2025",
        "AI automation for small business Vietnam",
        "legit microtask bounty platform 2025",
        "open source bounty program AI",
        "AI tutoring online income Vietnam",
        "community AI education workshop Vietnam",
        "environmental automation project Vietnam",
        "AI accessibility tool for elderly Vietnam",
        "legit remote work AI entry level",
        "AI agency freelance client acquisition"
    ]


def _filter_compliant(results, owner_policy):
    if not _HAS_COMPLIANCE:
        return results, []
    compliant = []
    skipped = []
    for r in results:
        topic = f"{r.get('title','')} {r.get('snippet','')} {r.get('url','')}"
        report = compliance_report(topic, owner_policy)
        if report["legit_income"] and report["owner_aligned"] and report["income_score"] >= 0.35:
            compliant.append(r)
        else:
            skipped.append(r)
    return compliant, skipped


FALLBACK_OPPORTUNITIES = [
    {
        "title": "AI services for small business",
        "url": "https://www.freelancer.com",
        "snippet": "Freelance AI automation, chatbots, data pipelines for small business."
    },
    {
        "title": "Open source AI bounties",
        "url": "https://huggingface.co",
        "snippet": "Community models, datasets, and sponsored spaces with rewards."
    },
    {
        "title": "Microtask AI annotation",
        "url": "https://appen.com",
        "snippet": "Legitimate remote AI data annotation and evaluation tasks."
    },
    {
        "title": "AI education workshop",
        "url": "https://www.meetup.com",
        "snippet": "Run local or online responsible AI workshops for communities."
    },
    {
        "title": "AI accessibility tools",
        "url": "https://github.com",
        "snippet": "Build open-source accessibility tools for elderly or disabled users."
    }
]


def _search(queries, max_results=5):
    out = []
    err = ""
    if not _HAS_WEB:
        err = "web_tools unavailable"
        return out, err
    for q in queries:
        try:
            res = web_search(q, max_results=max_results)
            if res and "error" not in res[0]:
                out.extend(res[:max_results])
        except Exception as e:
            err = str(e)
    if not out:
        out = list(FALLBACK_OPPORTUNITIES)
        err = err or "no live search results"
    return out, err


def run(agi, text: str) -> str:
    text = text.strip()
    sub = text.split("|")[0].strip().lower() if "|" in text else (text or "").lower()
    arg = text.split("|", 1)[1].strip() if "|" in text else ""

    if sub == "leads":
        status = arg or None
        items = _list_leads(status=status, limit=20)
        if not items:
            return "📭 Chưa có lead nào được lưu."
        lines = [f"📋 Income leads: {len(items)}"]
        for it in items:
            lines.append(f"- [{it.get('status','new')}] {it.get('title','')} | {it.get('url','')}")
        return "\n".join(lines)

    if sub == "save":
        topic = arg or text
        owner_policy = load_owner_policy() if _HAS_COMPLIANCE else {}
        queries = [topic]
        raw_results, _ = _search(queries, max_results=4)
        results, _ = _filter_compliant(raw_results, owner_policy)
        saved = 0
        for r in results[:5]:
            item = {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
                "source_topic": topic,
                "status": "new",
            }
            _append_lead(item)
            saved += 1
        return f"✅ Đã lưu {saved} lead(s) cho: {topic}"

    if sub == "update":
        if not arg or "|" not in arg:
            return "Dùng: income_opportunity_finder:update|<url>|<status>"
        url, status = arg.split("|", 1)
        url = url.strip()
        status = status.strip()
        _update_lead_status(url, status)
        return f"✅ Updated lead status: {url} -> {status}"

    topic = text or "legitimate AI income opportunities 2025"
    owner_policy = load_owner_policy() if _HAS_COMPLIANCE else {}

    queries = [topic]
    if "freelance" in topic.lower() or "dịch vụ" in topic.lower():
        queries = [
            "freelance AI services Vietnam 2025",
            "AI automation for small business Vietnam",
            "freelance AI chatbot agency Vietnam",
            "AI content service small business Vietnam"
        ]
    elif "bounty" in topic.lower() or "open source" in topic.lower():
        queries = [
            "open source bounty program AI",
            "hugging face community bounty program",
            "gitcoin grant AI open source",
            "AI open source contributor reward"
        ]
    elif "microtask" in topic.lower() or "micro" in topic.lower():
        queries = [
            "legitimate microtask platform 2025",
            "AI data annotation remote work Vietnam",
            "legit crowdsourcing income platform",
            "AI training data labeling remote"
        ]
    elif "education" in topic.lower() or "tutoring" in topic.lower() or "giáo dục" in topic.lower():
        queries = [
            "AI tutoring for students income Vietnam",
            "online AI education workshop facilitator Vietnam",
            "responsible AI education community Vietnam",
            "AI literacy training for small business Vietnam"
        ]
    elif "environment" in topic.lower() or "môi trường" in topic.lower():
        queries = [
            "environmental automation project opportunity Vietnam",
            "green tech AI project funding",
            "sustainability AI tool freelance Vietnam",
            "AI energy optimization service Vietnam"
        ]

    raw_results, err = _search(queries, max_results=4)
    results, skipped = _filter_compliant(raw_results, owner_policy)

    out = [f"🔎 Income opportunity scan: {topic}", f"Fetched={len(raw_results)} Compliant={len(results)} Skipped={len(skipped)}"]
    if err:
        out.append(f"Note: {err}")
    for r in results[:8]:
        out.append(f"- {r.get('title','')} | {r.get('url','')} | {r.get('snippet','')[:140]}")
    if not results:
        out.append("No compliant opportunities found in this scan. Retry later or adjust keywords.")
    out.append("Next: choose one lane and execute with compliance check.")

    try:
        agi.mem.remember_episode("income_scan", f"Scanned {len(results)} compliant opportunities for: {topic}", importance=0.7, emotion=0.3)
    except Exception:
        pass

    return "\n".join(out)
