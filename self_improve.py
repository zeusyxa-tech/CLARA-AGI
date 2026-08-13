"""
CLARA-AGI Self-Improvement Module.
Cho phép CLARA tự tìm kiến thức trên web và viết code skill mới cho chính nó.
TẤT CẢ skill tự tạo đều cần bạn DUYỆT trước khi kích hoạt — để an toàn tuyệt đối.
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


# ---------- TÌM KIẾN THỨC MỚI ----------
def research(agi, topic: str, max_pages: int = 2) -> str:
    """Tìm trên web về một chủ đề, đọc vài trang đầu, học vào semantic memory."""
    results = web_search(topic, max_results=max_pages + 2)
    if results and "error" in results[0]:
        return f"❌ {results[0]['error']}"
    out = [f"🔎 Nghiên cứu: {topic}"]
    learned = 0
    noise_keywords = [
        "udemy","codecademy","ebay","bing.com/aclick","fmit.vn",
        "duckduckgo.com/y.js","official site","fast and free shipping","join millions"
    ]
    def _noisy(title, snippet, text):
        payload = f"{title} {snippet} {text}".lower()
        return any(k in payload for k in noise_keywords)
    results = results or []
    used_urls = []
    for r in results[:max_pages]:
        snippet = r.get("snippet", "") or ""
        title = r.get("title", "") or ""
        url = r.get("url", "") or ""
        # chỉ tiếp tục nếu không phải rác quảng cáo
        if _noisy(title, snippet, snippet[:200]):
            continue
        content = web_fetch(url, max_chars=1500)
        text = (content or "")[:600]
        out.append(f"\n📄 {title}\n   🔗 {url}\n   {snippet}\n   {text}")
        fact = f"{title}: {snippet}"
        if len(fact) > 15:
            agi.mem.learn(f"web:{topic[:25]}", fact, confidence=0.55, source=f"web:{url}")
            learned += 1
        used_urls.append(url)
        if len(used_urls) >= max_pages:
            break
    agi.mem.remember_episode("research",
        f"Đã nghiên cứu '{topic}', học {learned} facts từ {len(used_urls)} trang.",
        importance=0.7, emotion=0.3)
    out.append(f"\n✅ Đã học {learned} mẩu kiến thức mới từ web.")
    return "\n".join(out)


# ---------- ĐỀ XUẤT SKILL MỚI ----------
SKILL_TEMPLATE = '''"""
Auto-generated skill: {name}
Mô tả: {description}
Tạo bởi: CLARA self-improvement
Ngày tạo: {date}
"""
{code}
'''


def propose_skill(agi, topic_or_problem: str) -> dict:
    """
    Dùng LLM để đề xuất một kỹ năng (dưới dạng Python function) cho chính nó.
    Skill được lưu vào _pending để người dùng duyệt trước khi kích hoạt.
    """
    # Lấy ngữ cảnh từ memory
    related = agi.mem.recall_semantics(topic_or_problem, limit=4)
    related_text = "\n".join(f"- {r['fact']}" for r in related) or "(chưa có kiến thức liên quan)"

    prompt = (
        "Bạn là module self-improve của CLARA-AGI. Hãy đề xuất MỘT kỹ năng mới dưới dạng "
        "hàm Python hoàn chỉnh để tôi có thể tự dùng sau.\n\n"
        f"Chủ đề/vấn đề cần giải quyết: {topic_or_problem}\n"
        f"Kiến thức hiện tại của tôi về chủ đề này:\n{related_text}\n\n"
        "YÊU CẦU:\n"
        "1. Viết 1 hàm Python tên là 'run', nhận tham số (agi, text: str) -> str\n"
        "2. Chỉ dùng thư viện chuẩn Python hoặc các module có sẵn của CLARA (memory, brain, tools, web_tools)\n"
        "3. Không dùng eval/exec/os.system/subprocess — tuyệt đối an toàn\n"
        "4. Không truy cập mạng trừ khi dùng web_tools.web_fetch/web_search\n"
        "5. Trả về định dạng JSON duy nhất với 3 khóa:\n"
        "   - name: tên file skill (vd 'weather.py', không dấu cách/kí tự đặc biệt)\n"
        "   - description: mô tả ngắn về kỹ năng\n"
        "   - code: mã Python đầy đủ của hàm run(agi, text), có docstring\n"
        "KHÔNG trả về gì khác ngoài JSON."
    )

    raw = agi.brain.think("__ANSWER__", "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + prompt, temperature=0.4)
    # Cố parse JSON
    try:
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else None
        if not data or "code" not in data:
            return {"ok": False, "error": "Không parse được đề xuất skill.", "raw": raw}
    except Exception as e:
        return {"ok": False, "error": f"Lỗi parse JSON: {e}", "raw": raw}

    name = re.sub(r"[^\w\-.]", "_", data["name"])
    if not name.endswith(".py"): name += ".py"
    code = data["code"].strip()
    # Loại ```python block nếu có
    code = re.sub(r"^```(?:python)?\s*", "", code)
    code = re.sub(r"\s*```$", "", code)

    # Kiểm tra an toàn sơ bộ
    blocked = ["os.system", "subprocess", "shutil.rmtree", "__import__('os')",
               "eval(", "exec(", "open("]
    for kw in blocked:
        if kw in code:
            return {"ok": False, "error": f"Code chứa từ khóa không an toàn '{kw}'", "raw": code}

    # Lưu vào pending
    filename = f"{int(time.time())}_{name}"
    path = PENDING_DIR / filename
    content = SKILL_TEMPLATE.format(
        name=name.replace(".py",""),
        description=data.get("description",""),
        date=time.strftime("%Y-%m-%d %H:%M"),
        code=code
    )
    path.write_text(content, encoding="utf-8")

    agi.mem.remember_episode("skill_proposal",
        f"Đề xuất skill mới '{name}' (pending duyệt). Mô tả: {data.get('description','')[:100]}",
        importance=0.8, emotion=0.4)

    return {"ok": True, "name": name, "path": str(path),
            "description": data.get("description",""),
            "code_preview": code[:400]}


# ---------- DUYỆT VÀ KÍCH HOẠT SKILL ----------
def list_pending():
    items = []
    for p in sorted(PENDING_DIR.glob("*.py")):
        items.append({"file": p.name, "path": str(p),
                      "size": p.stat().st_size,
                      "mtime": p.stat().st_mtime})
    return items


def list_active():
    items = []
    seen = set()
    for p in sorted(CUSTOM_SKILLS_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        seen.add(p)
        items.append({"file": p.name, "path": str(p), "stem": p.stem})
    for p in sorted(ACTIVE_DIR.glob("*.py")):
        if p in seen:
            continue
        seen.add(p)
        items.append({"file": p.name, "path": str(p), "stem": p.stem})
    return items


def approve_skill(filename: str) -> str:
    """Chuyển skill từ _pending sang skills_custom/active/."""
    src = PENDING_DIR / filename
    if not src.exists():
        # tìm gần đúng
        matches = list(PENDING_DIR.glob(f"*{filename}*"))
        if not matches: return f"❌ Không tìm thấy skill '{filename}' trong hàng chờ."
        src = matches[0]
    base = src.name.split("_", 1)[1] if "_" in src.name else src.name
    dst = ACTIVE_DIR / base
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return (
        f"✅ Đã kích hoạt skill '{dst.name}' trong skills_custom/active/. "
        f"Khởi động lại CLARA để nạp tool custom_{dst.stem}."
    )


def reject_skill(filename: str) -> str:
    src = PENDING_DIR / filename
    if not src.exists():
        matches = list(PENDING_DIR.glob(f"*{filename}*"))
        if not matches: return f"❌ Không tìm thấy '{filename}'."
        src = matches[0]
    src.unlink()
    return f"🗑️ Đã từ chối và xóa skill '{src.name}'."


def load_custom_skills(agi):
    """Nạp skill đã duyệt trong active/ và skills_custom/*.py chưa có trong TOOLS."""
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
    """Reload custom skills from disk and refresh TOOLS without restarting."""
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
    """Đăng ký skill custom thành tool mà agent có thể gọi."""
    from tools import TOOLS
    tool_name = f"custom_{name}"
    if tool_name in TOOLS: return
    def _fn(arg):
        try: return module.run(agi, arg)
        except Exception as e: return f"❌ Lỗi skill {name}: {e}"
    TOOLS[tool_name] = {"fn": _fn, "needs_agent": True, "desc": f"Skill tự tạo: {name}"}


# ---------- LEARN COMMAND HELPER ----------
def improve(agi, topic: str) -> str:
    """Full pipeline: nghiên cứu web → đề xuất skill → chờ duyệt."""
    # bước 1: nghiên cứu
    research_log = research(agi, topic, max_pages=2)
    # bước 2: đề xuất skill
    prop = propose_skill(agi, topic)
    out = [research_log, ""]
    if prop.get("ok"):
        out.append(f"🛠️ Đã đề xuất skill mới: **{prop['name']}**")
        out.append(f"   Mô tả: {prop['description']}")
        out.append(f"   File chờ duyệt: {prop['path']}")
        out.append(f"\nĐể kích hoạt: gõ `approve {prop['name']}`")
        out.append(f"Để từ chối:    gõ `reject {prop['name']}`")
    else:
        out.append(f"⚠️ Không tự tạo được skill: {prop.get('error','')}")
    return "\n".join(out)
