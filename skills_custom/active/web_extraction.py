#!/usr/bin/env python3
"""
CLARA-AGI Skill: web_extraction
Trích xuất cấu trúc: heading, table, list, link từ HTML text.
"""
import re


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: web_extract:<subcmd>|<html_or_text>\n"
                "  headings               extract H1..H6\n"
                "  tables                 extract table rows as TSV\n"
                "  links                  href + anchor text\n"
                "  lists:<marker>         extract list items\n"
                "  meta:<attr>            extract simple attributes")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    try:
        if sub.startswith("headings"):
            tags = re.findall(r"<h([1-6])[^>]*>(.*?)</h\1>", payload, re.S|re.I)
            if not tags: return "(no headings)"
            return "\n".join(f"H{level}: {re.sub(r'<[^>]+>','',text).strip()}" for level,text in tags[:30])
        if sub.startswith("tables"):
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", payload, re.S|re.I)
            out = []
            for row in rows[:20]:
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S|re.I)
                out.append("\t".join(re.sub(r"<[^>]+>","",c).strip() for c in cells))
            return "\n".join(out) or "(no tables)"
        if sub.startswith("links"):
            links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', payload, re.S|re.I)
            return "\n".join(f"{href}\t{re.sub(r'<[^>]+>','',txt).strip()}" for href,txt in links[:50])
        if sub.startswith("lists"):
            marker = sub.split(":",1)[1].strip() if ":" in sub else None
            if marker:
                items = re.findall(rf"<li[^>]*>.*?</li>", payload, re.S|re.I)
                out = []
                for it in items[:30]:
                    if marker.lower() in it.lower():
                        out.append(re.sub(r"<[^>]+>","",it).strip())
                return "\n".join(out) or "(no matching list items)"
            else:
                items = re.findall(r"<li[^>]*>(.*?)</li>", payload, re.S|re.I)
                return "\n".join(re.sub(r"<[^>]+>","",x).strip() for x in items[:30])
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
