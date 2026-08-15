"""
CLARA-AGI v1.3 - Self-Improvement: web research, skill proposal, auto-approval.
"""
import os, re, json, time
from pathlib import Path
from web_tools import web_search, web_fetch

CUSTOM_SKILLS_DIR = Path(__file__).parent / "skills_custom"
CUSTOM_SKILLS_DIR.mkdir(exist_ok=True)
ACTIVE_DIR = CUSTOM_SKILLS_DIR / "active"
ACTIVE_DIR.mkdir(exist_ok=True)
PENDING_DIR = CUSTOM_SKILLS_DIR / "_pending"
PENDING_DIR.mkdir(exist_ok=True)

MAX_PAGES_DEFAULT = 3
MAX_FACTS_PER_PAGE = 5
MIN_CONFIDENCE = 0.5
DEDUP_SIMILARITY_THRESHOLD = 0.85


# ---------- Knowledge helpers ----------
def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\sÀ-ỹ]", "", s, flags=re.UNICODE)
    return s


def _dedup(agi, new_facts):
    out = []
    for f in new_facts:
        nf = _normalize(f)
        hits = agi.mem.recall_semantics(nf, limit=3)
        best = max((r.get("confidence", 0) for r in hits), default=0)
        if best < DEDUP_SIMILARITY_THRESHOLD:
            out.append(f)
    return out


# ---------- Web research ----------
def research(agi, topic: str, max_pages: int = MAX_PAGES_DEFAULT) -> str:
    results = web_search(topic, max_results=max_pages + 2)
    if results and "error" in results[0]:
        return f"❌ {results[0]['error']}"

    noise_keywords = [
        "udemy", "codecademy", "ebay", "bing.com/aclick", "fmit.vn",
        "duckduckgo.com/y.js", "official site", "fast and free shipping",
        "join millions", "course", "khóa học", "bán ", "mua ", "giảm giá"
    ]

    def _noisy(title, snippet, text):
        payload = f"{title} {snippet} {text}".lower()
        return any(k in payload for k in noise_keywords)

    results = results or []
    used_urls = []
    learned = 0
    buffer = []

    for r in results[:max_pages]:
        snippet = (r.get("snippet") or "").strip()
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        if _noisy(title, snippet, snippet[:200]):
            continue
        content = web_fetch(url, max_chars=2500) or ""
        text = content[:900]
        if len(text) < 60:
            continue
        buffer.append((title, url, snippet, text))
        used_urls.append(url)
        if len(used_urls) >= max_pages:
            break

    facts = []
    for title, url, snippet, text in buffer:
        facts.append((f"{title}: {snippet}", url))
        facts.append((f"{title} | chi tiết: {text[:220]}", url))
        facts.append((f"Nguồn {title}: {text[220:440]}", url))

    seen = set()
    deduped = []
    for text, url in facts[:MAX_FACTS_PER_PAGE * max_pages]:
        key = _normalize(text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((text, url))

    text_to_url = {text: url for text, url in deduped}
    deduped_texts = _dedup(agi, list(text_to_url.keys()))
    deduped = [(text, text_to_url.get(text, "")) for text in deduped_texts]

    for fact_text, url in deduped:
        if len(fact_text) > 15 and url:
            agi.mem.learn(f"web:{_normalize(topic)[:25]}", fact_text, confidence=MIN_CONFIDENCE, source=f"web:{url}")
            learned += 1

    agi.mem.remember_episode("research",
        f"Đã nghiên cứu '{topic}', học {learned} facts từ {len(used_urls)} trang.",
        importance=0.8, emotion=0.3)

    lines = [f"🔎 Nghiên cứu: {topic}", f"✅ Học {learned} facts từ {len(used_urls)} trang."]
    for title, url, snippet, _ in buffer[:max_pages]:
        lines.append(f"📄 {title}\n   🔗 {url}\n   {snippet}\n")
    return "\n".join(lines)


# ---------- Skill proposal ----------
SKILL_TEMPLATE = '''"""
Auto-generated skill: {name}
Mô tả: {description}
Tạo bởi: CLARA self-improvement
Ngày tạo: {date}
"""
{code}
'''

BLOCKED_PATTERNS = [
    "os.system", "subprocess", "shutil.rmtree", "__import__('os')",
    "eval(", "exec(", "open(", "requests.post", "requests.get", "urllib",
    "socket.", "http.client", "ftplib", "telnetlib", "xmlrpc",
    "pickle.loads", "yaml.load(", "tempfile.mktemp", "globals()", "locals()",
]


def _safe_code(code: str) -> bool:
    c = code.lower()
    return not any(p in c for p in BLOCKED_PATTERNS)


def propose_skill(agi, topic_or_problem: str) -> dict:
    related = agi.mem.recall_semantics(topic_or_problem, limit=5)
    related_text = "\n".join(f"- {r['fact']}" for r in related) or "(chưa có kiến thức liên quan)"

    prompt = (
        "Bạn là module self-improve của CLARA-AGI. Hãy đề xuất MỘT kỹ năng mới dưới dạng "
        "hàm Python hoàn chỉnh để tôi có thể tự dùng sau.\n\n"
        f"Chủ đề/vấn đề cần giải quyết: {topic_or_problem}\n"
        f"Kiến thức hiện tại của tôi về chủ đề này:\n{related_text}\n\n"
        "YÊU CẦU:\n"
        "1. Viết 1 hàm Python tên là 'run', nhận tham số (agi, text: str) -> str\n"
        "2. Chỉ dùng thư viện chuẩn Python hoặc các module có sẵn của CLARA (memory, brain, tools, web_tools, compliance)\n"
        "3. Tuyệt đối không dùng eval/exec/os.system/subprocess, không mở kết nối mạng trừ web_tools\n"
        "4. Hãy tận dụng tối đa kiến thức trong chủ đề để tạo công cụ thực tế cho CLARA\n"
        "5. Trả về định dạng JSON duy nhất với 3 khóa:\n"
        "   - name: tên file skill (vd 'datetime_handling.py', không dấu cách/kí tự đặc biệt)\n"
        "   - description: mô tả ngắn\n"
        "   - code: mã Python đầy đủ của hàm run(agi, text), có docstring\n"
        "KHÔNG trả về gì khác ngoài JSON."
    )

    raw = agi.brain.think("__ANSWER__", "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + prompt, temperature=0.35)
    try:
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else None
        if not data or "code" not in data:
            return {"ok": False, "error": "Không parse được đề xuất skill.", "raw": raw}
    except Exception as e:
        return {"ok": False, "error": f"Lỗi parse JSON: {e}", "raw": raw}

    name = re.sub(r"[^\w\-. ]", "_", data["name"].strip())
    name = name.replace(" ", "_")
    if not name.endswith(".py"):
        name += ".py"
    code = data["code"].strip()
    code = re.sub(r"^```(?:python)?\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    if not _safe_code(code):
        return {"ok": False, "error": "Code chứa mẫu không an toàn.", "raw": code}

    filename = f"{int(time.time())}_{name}"
    path = PENDING_DIR / filename
    content = SKILL_TEMPLATE.format(
        name=name.replace(".py", ""),
        description=data.get("description", ""),
        date=time.strftime("%Y-%m-%d %H:%M"),
        code=code
    )
    path.write_text(content, encoding="utf-8")

    agi.mem.remember_episode("skill_proposal",
        f"Đề xuất skill mới '{name}' (pending duyệt). Mô tả: {data.get('description','')[:120]}",
        importance=0.85, emotion=0.4)

    return {"ok": True, "name": name, "path": str(path),
            "description": data.get("description", ""),
            "code_preview": code[:400]}


# ---------- Approval / activation ----------
def list_pending():
    items = []
    for p in sorted(PENDING_DIR.glob("*.py")):
        items.append({"file": p.name, "path": str(p), "size": p.stat().st_size, "mtime": p.stat().st_mtime})
    return items


def list_active():
    items, seen = [], set()
    for root in (CUSTOM_SKILLS_DIR, ACTIVE_DIR):
        for p in sorted(root.glob("*.py")):
            if p.name == "__init__.py":
                continue
            if p in seen:
                continue
            seen.add(p)
            items.append({"file": p.name, "path": str(p), "stem": p.stem})
    return items


def approve_skill(filename: str) -> str:
    src = PENDING_DIR / filename
    if not src.exists():
        matches = list(PENDING_DIR.glob(f"*{filename}*"))
        if not matches:
            return f"❌ Không tìm thấy skill '{filename}' trong hàng chờ."
        src = matches[0]
    base = src.name.split("_", 1)[1] if "_" in src.name else src.name
    dst = ACTIVE_DIR / base
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return (
        f"✅ Đã kích hoạt skill '{dst.name}' trong skills_custom/active/. "
        "Khởi động lại CLARA để nạp tool custom_" + dst.stem + "."
    )


def reject_skill(filename: str) -> str:
    src = PENDING_DIR / filename
    if not src.exists():
        matches = list(PENDING_DIR.glob(f"*{filename}*"))
        if not matches:
            return f"❌ Không tìm thấy '{filename}'."
        src = matches[0]
    src.unlink()
    return f"🗑️ Đã từ chối và xóa skill '{src.name}'."


def load_custom_skills(agi):
    import importlib.util
    loaded = []
    roots = [ACTIVE_DIR, CUSTOM_SKILLS_DIR]
    for root in roots:
        for p in sorted(root.glob("*.py")):
            if p.name == "__init__.py":
                continue
            tool_name = f"custom_{p.stem}"
            from tools import TOOLS
            if tool_name in TOOLS:
                continue
            try:
                spec = importlib.util.spec_from_file_location(tool_name, str(p))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "run"):
                    loaded.append(p.name)
                    _register_custom_tool(agi, p.stem, mod)
            except Exception as e:
                try:
                    agi.mem.remember_episode("skill_error",
                        f"Lỗi nạp skill {p.name}: {e}", importance=0.6, emotion=-0.3)
                except Exception:
                    pass
    return loaded


def reload_skills(agi):
    import importlib.util
    from tools import TOOLS
    reloaded = []
    roots = [ACTIVE_DIR, CUSTOM_SKILLS_DIR]
    for root in roots:
        for p in sorted(root.glob("*.py")):
            if p.name == "__init__.py":
                continue
            tool_name = f"custom_{p.stem}"
            old = TOOLS.pop(tool_name, None)
            try:
                spec = importlib.util.spec_from_file_location(tool_name, str(p))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "run"):
                    _register_custom_tool(agi, p.stem, mod)
                    reloaded.append(p.name)
            except Exception as e:
                if old is not None:
                    TOOLS[tool_name] = old
                try:
                    agi.mem.remember_episode("skill_error",
                        f"Lỗi reload skill {p.name}: {e}", importance=0.6, emotion=-0.3)
                except Exception:
                    pass
    return reloaded


def _register_custom_tool(agi, name, module):
    from tools import TOOLS
    tool_name = f"custom_{name}"
    if tool_name in TOOLS:
        return
    def _fn(arg):
        try:
            return module.run(agi, arg)
        except Exception as e:
            return f"❌ Lỗi skill {name}: {e}"
    TOOLS[tool_name] = {"fn": _fn, "needs_agent": True, "desc": f"Skill tự tạo: {name}"}


# ---------- Full pipeline ----------
def improve(agi, topic: str) -> str:
    research_log = research(agi, topic, max_pages=MAX_PAGES_DEFAULT)
    prop = propose_skill(agi, topic)
    out = [research_log, ""]
    if prop.get("ok"):
        out.append(f"🛠️ Đã đề xuất skill mới: {prop['name']}")
        out.append(f"   Mô tả: {prop['description']}")
        out.append(f"   File chờ duyệt: {prop['path']}")
        out.append(f"\nĐể kích hoạt: gõ `approve {prop['name']}`")
        out.append(f"Để từ chối:    gõ `reject {prop['name']}`")
    else:
        out.append(f"⚠️ Không tự tạo được skill: {prop.get('error','')}")
    return "\n".join(out)
