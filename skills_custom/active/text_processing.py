#!/usr/bin/env python3
"""
CLARA-AGI Skill: text_processing
Xử lý text: lowercase, uppercase, strip, replace, regex split, count, sort unique.
"""
import re


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: text:<subcmd>|<text>\n"
                "  lower|upper|strip|title|<src>|<dst>|replace\n"
                "  regex:<pattern>|<repl>|<text>\n"
                "  split:<sep>|<text>   count:<text>   unique:<text>   lines:<text>")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    try:
        if sub == "lower":
            return payload.lower()
        if sub == "upper":
            return payload.upper()
        if sub == "strip":
            return payload.strip()
        if sub == "title":
            return payload.title()
        if sub.startswith("replace"):
            # replace:<old>|<new>|<text>
            rr = sub + "|" + payload
            _, old, new, txt = rr.split("|", 3)
            return txt.replace(old, new)
        if sub.startswith("regex"):
            # regex:<pattern>|<replacement>|<text>
            rr = sub + "|" + payload
            _, pattern, repl, txt = rr.split("|", 3)
            return re.sub(pattern, repl, txt)
        if sub.startswith("split"):
            sep, txt = payload.split("|", 1) if "|" in payload else ("\n", payload)
            items = [x.strip() for x in txt.split(sep) if x.strip()]
            return "\n".join(f"{i+1}. {x}" for i, x in enumerate(items[:200]))
        if sub == "count":
            return str(len(payload))
        if sub == "unique":
            items = list(dict.fromkeys(payload.splitlines()))
            return "\n".join(items[:200])
        if sub == "lines":
            return "\n".join(payload.splitlines()[:200])
        return f"❌ Unknown text subcmd: {sub}"
    except Exception as e:
        return f"❌ {e}"
