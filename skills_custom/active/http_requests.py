#!/usr/bin/env python3
"""
CLARA-AGI Skill: http_requests
HTTP GET/POST JSON an toàn. Chặn file://, localhost, timeout 15s.
"""
import urllib.request, urllib.error, json as _json


UA = "CLARA-AGI-http-requests/1.0"
TIMEOUT = 15


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: http:<method>|<url>\n  http:POST|<url>|<json>\n"
                "Chặn: file://, localhost, 127.*, ::1")
    parts = text.split("|", 1)
    method = parts[0].strip().upper()
    rest = parts[1] if len(parts) > 1 else ""
    url = rest.strip().split("\n", 1)[0].strip()
    body = None
    if "|" in rest:
        _, body_raw = rest.split("|", 1)
        body_raw = body_raw.strip()
        if body_raw:
            body = body_raw.encode("utf-8")
            if "application/json" not in (text.split("|")[1] if len(text.split("|")) > 1 else ""):
                if body.strip().startswith("{") or body.strip().startswith("["):
                    pass
    blocked = ("file://", "localhost", "127.", "::1")
    low = url.lower()
    if any(b in low for b in blocked):
        return "❌ Chặn truy cập nội bộ."
    if not url.startswith("http"): url = "https://" + url
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": UA, "Accept": "application/json,text/html,*/*;q=0.8",
        "Content-Type": "application/json" if body else "text/plain",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            data = r.read()
            if "json" in ctype:
                try: return _json.dumps(_json.loads(data), ensure_ascii=False, indent=2)
                except Exception: pass
            txt = data.decode("utf-8", errors="replace")[:4000]
            return txt
    except urllib.error.HTTPError as e:
        return f"❌ HTTP {e.code}: {e.reason}"
    except Exception as e:
        return f"❌ {e}"
