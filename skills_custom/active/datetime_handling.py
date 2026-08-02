#!/usr/bin/env python3
"""
CLARA-AGI Skill: datetime_handling
Xử lý ngày giờ, timezone, format, delta, parse đơn giản.
"""
import datetime as dt
from pathlib import Path


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: dt:<subcmd>|<arg>\n"
                "  now|today<timezone>    now in TZ\n"
                "  parse:<fmt>|<string>   parse text\n"
                "  fmt:<fmt>|<dt>|.<tz>  format datetime\n"
                "  delta:<start>|<end>|<fmt>  diff\n"
                "  add:<field>:<val>|<dt>|<fmt>  add/sub\n"
                "  list-formats           preset formats")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    tz_default = dt.timezone.utc
    try:
        if sub == "now":
            tz_name = payload.strip() or "UTC"
            import zoneinfo
            try: tz = zoneinfo.ZoneInfo(tz_name)
            except Exception: tz = tz_default
            now = dt.datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        if sub.startswith("parse"):
            _, fmt, s = text.split("|", 2)
            return str(dt.datetime.strptime(s.strip(), fmt.strip()))
        if sub.startswith("fmt"):
            try:
                fmt, s, tz_name = text.split("|", 2)
            except ValueError:
                fmt, s = text.split("|", 1); tz_name = "UTC"
            d = dt.datetime.fromisoformat(s.strip())
            import zoneinfo
            try: d = d.astimezone(zoneinfo.ZoneInfo(tz_name.strip()))
            except Exception: pass
            return d.strftime(fmt.strip())
        if sub.startswith("delta"):
            _, start_s, end_s, fmt = text.split("|", 3)
            fmt = fmt.strip() or "%Y-%m-%d %H:%M:%S"
            s = dt.datetime.strptime(start_s.strip(), fmt)
            e = dt.datetime.strptime(end_s.strip(), fmt)
            delta = e - s
            return str(delta) + f" ({delta.days}d {delta.seconds//3600}h)"
        if sub.startswith("add"):
            _, field_val, s, fmt = text.split("|", 3)
            field, val = field_val.split(":", 1)
            d = dt.datetime.strptime(s.strip(), fmt.strip())
            if field == "days": d += dt.timedelta(days=int(val))
            elif field == "hours": d += dt.timedelta(hours=int(val))
            elif field == "minutes": d += dt.timedelta(minutes=int(val))
            elif field == "weeks": d += dt.timedelta(weeks=int(val))
            else: return f"❌ field: days|hours|minutes|weeks"
            return d.strftime(fmt.strip())
        if sub == "list-formats":
            return "\n".join(["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%H:%M", "%A, %d %B %Y"])
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
