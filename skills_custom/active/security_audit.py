#!/usr/bin/env python3
"""
CLARA-AGI Skill: security_audit
Lightweight security checks: input validation, secret exposure, dependency safety.
"""
import re, pathlib


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return "Usage: sec:<subcmd>|<path>\n  scan:<path>   quick secret/input validation audit\n  check:<pattern>|<text>   regex danger search"
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub.startswith("scan"):
            target = pathlib.Path(arg.strip() or "workspace")
            if not target.exists():
                return f"❌ missing {target}"
            findings = []
            dangerous = ["eval(", "exec(", "__import__(", "os.system(", "subprocess", "pickle.loads", "yaml.load("]
            secret_patterns = [
                r"AIza[0-9A-Za-z\\-_]{35}", r"sk-[A-Za-z0-9]{20,}", r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
                r"[a-f0-9]{32,}", r"(mongodb|postgres|mysql)://[^\\s]+",
            ]
            files = list(target.rglob("*.py"))[:20]
            for fp in files:
                txt = fp.read_text(encoding="utf-8", errors="replace")
                for d in dangerous:
                    if d in txt:
                        findings.append(f"dangerous_call:{d} in {fp.name}")
                for pat in secret_patterns:
                    if re.search(pat, txt):
                        findings.append(f"possible_secret:{pat} in {fp.name}")
            return "\n".join(findings[:20]) if findings else "✅ No obvious issues found."
        if sub.startswith("check"):
            if "|" not in arg:
                return "❌ check:<pattern>|<text>"
            pat, txt = arg.split("|", 1)
            hits = re.findall(pat, txt)
            return f"Pattern hits: {len(hits)}\n" + "\n".join(hits[:10]) if hits else "(no hits)"
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
