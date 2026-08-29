#!/usr/bin/env python3
"""
CLARA-AGI Skill: deep_research
Multi-source research: search + fetch + summarize + store facts.
"""
import re


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return "Usage: research:<query>|<max_pages:int>"
    query, _, rest = text.partition("|")
    max_pages = int(rest.strip() or "2")
    try:
        from web_tools import web_search, web_fetch
    except Exception as e:
        return f"❌ web tools unavailable: {e}"
    results = web_search(query.strip(), max_results=max_pages + 2)
    if results and "error" in results[0]:
        return f"❌ {results[0]['error']}"
    learned = 0
    bits = []
    for r in results[:max_pages]:
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "") or ""
        content = web_fetch(url, max_chars=1800) or ""
        text_content = (content or "")[:500]
        bits.append(f"📄 {title}\n🔗 {url}\n{snippet}\n{text_content}")
        fact = f"{title}: {snippet}"
        if len(fact) > 15:
            agi.mem.learn(f"web:{query[:25]}", fact, confidence=0.55, source=f"web:{url}")
            learned += 1
    agi.mem.remember_episode("research", f"Đã nghiên cứu '{query}', học {learned} facts.", importance=0.7, emotion=0.3)
    return "\n\n---\n\n".join(bits) + f"\n\n✅ Đã học {learned} mẩu kiến thức."
