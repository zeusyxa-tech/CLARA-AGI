#!/usr/bin/env python3
"""
CLARA-AGI Skill: json_processing
Parse, validate, pretty, path query, minify, set/get JSON đơn giản.
"""
import json


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: json:<subcmd>|<arg>\n"
                "  parse:<json_text>   validate + pretty print\n"
                "  get:<path>|<json>   jq-like simple path\n"
                "  set:<path>|<value>|<json>   insert at path\n"
                "  minify:<json>       compact JSON\n"
                "  types:<json>        list types by path")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    try:
        if sub.startswith("parse"):
            data = json.loads(payload.strip())
            return json.dumps(data, ensure_ascii=False, indent=2)
        if sub.startswith("validate"):
            try:
                json.loads(payload.strip())
                return "✅ JSON hợp lệ"
            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON: {e}"
        if sub.startswith("pretty"):
            data = json.loads(payload.strip())
            return json.dumps(data, ensure_ascii=False, indent=2)
        if sub.startswith("minify"):
            data = json.loads(payload.strip())
            return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        if sub.startswith("types"):
            data = json.loads(payload.strip())
            def walk(obj, path="root"):
                if isinstance(obj, dict):
                    if path != "root": yield f"{path} (object) {len(obj)} keys"
                    for k,v in obj.items(): yield from walk(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    if path != "root": yield f"{path} (array[{len(obj)}])"
                    for i,v in enumerate(obj[:20]): yield from walk(v, f"{path}[{i}]")
                else:
                    if path != "root": yield f"{path} ({type(obj).__name__})"
            return "\n".join(list(walk(data))[:80])
        if sub.startswith("get"):
            path, raw = text.split("|", 2)[1], text.split("|", 2)[2] if text.count("|") > 1 else payload
            ptr = json.loads(raw)
            for p in path.lstrip(".").split("."):
                if not p: continue
                if isinstance(ptr, dict): ptr = ptr[p]
                elif isinstance(ptr, list) and p.isdigit(): ptr = ptr[int(p)]
                else: return f"❌ path không hợp lệ: {p}"
            return json.dumps(ptr, ensure_ascii=False, indent=2) if isinstance(ptr, (dict, list)) else str(ptr)
        if sub.startswith("set"):
            path, value, raw = text.split("|", 2)[1], text.split("|", 2)[2], text.split("|", 2)[2] if text.count("|") > 1 else payload
            # loose: set:<path>|<value>|<json>
            sep = payload.split("|", 1)
            if len(sep) == 2:
                path, rest = payload.split("|", 1)
                value_s, raw_s = rest.split("|", 1)
            else:
                return "❌ set:<path>|<value>|<json>"
            ptr = json.loads(raw_s.strip())
            keys = path.lstrip(".").split(".")
            o = ptr
            for k in keys[:-1]:
                o = o[k] if isinstance(o, dict) else o[int(k)]
            k = keys[-1]
            try:
                v = json.loads(value_s)
            except Exception:
                v = value_s
            if isinstance(o, dict): o[k] = v
            elif isinstance(o, list) and k.isdigit(): o[int(k)] = v
            else: return "❌ target không phải object/array"
            return json.dumps(ptr, ensure_ascii=False, indent=2)
        return "❌ subcmd unknown"
    except json.JSONDecodeError as e:
        return f"❌ JSON lỗi: {e}"
    except Exception as e:
        return f"❌ {e}"
