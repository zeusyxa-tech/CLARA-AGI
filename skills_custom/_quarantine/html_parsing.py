#!/usr/bin/env python3
"""
CLARA-AGI Skill: html_parsing
DOM query đơn giản: tag, class, attr extractor từ raw HTML.
"""
import re


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: html:<subcmd>|<payload>\n"
                "  tag:<name>|<html>               extract tag inner text\n"
                "  class:<class>|<html>            extract all by class\n"
                "  attr:<tag>:<attr>|<html>        extract attribute values\n"
                "  text:<tag>|<html>               tag -> plain text\n"
                "  ids:<html>                      all ids")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    try:
        if sub.startswith("tag:"):
            _, name = sub.split(":", 1)
            hits = re.findall(rf"<{name}[^>]*>(.*?)</{name}>", payload, re.S|re.I)
            return "\n".join(h[:5] for h in hits[:20]) or "(no matches)"
        if sub.startswith("class:"):
            _, cls = sub.split(":", 1)
            hits = re.findall(rf'class=["\'][^"\']*\b{re.escape(cls)}\b[^"\']*["\'][^>]*>(.*?)</[^>]+>', payload, re.S|re.I)
            return "\n".join(re.sub(r"<[^>]+>","", h).strip() for h in hits[:20]) or "(no matches)"
        if sub.startswith("attr:"):
            _, tag_attr = sub.split(":", 1)
            tag, attr = tag_attr.split(":", 1)
            hits = re.findall(rf"<{tag}[^>]*\b{re.escape(attr)}=[\"']([^\"']*)[\"'][^>]*>", payload, re.I)
            return "\n".join(hits[:20]) or "(no matches)"
        if sub.startswith("text:"):
            _, name = sub.split(":", 1)
            hits = re.findall(rf"<{name}[^>]*>(.*?)</{name}>", payload, re.S|re.I)
            return "\n".join(re.sub(r"<[^>]+>"," ",h).strip() for h in hits[:20]) or "(no matches)"
        if sub == "ids":
            ids = re.findall(r'\bid=["\']([^"\']+)["\']', payload, re.I)
            return "\n".join(dict.fromkeys(ids)) or "(no ids)"
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
