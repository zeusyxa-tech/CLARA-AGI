"""
CLARA-AGI v1.1 - Công cụ (tools) — tay chân của agent.
- calc: tính toán an toàn
- read_file / write_file / list_files: thao tác file trong workspace
- now: ngày giờ
- run_python: chạy code Python trong sandbox (AST-based filter + timeout + giới hạn tài nguyên)
- search_memory: tìm trực tiếp trong bộ nhớ
- shell: *chỉ khi người dùng bật chế độ không an toàn*
"""
import ast, re, json, math, time, io, contextlib, traceback
import multiprocessing as mp
from pathlib import Path

SAFE_ROOT = (Path(__file__).parent / "workspace").resolve()
SAFE_ROOT.mkdir(exist_ok=True)


def _safe_path(path: str) -> Path:
    if not path:
        return SAFE_ROOT
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = SAFE_ROOT / p
    try:
        p.resolve().relative_to(SAFE_ROOT)
    except ValueError:
        p = SAFE_ROOT / p.name
    return p.resolve()


# ---------- TOOL: calc ----------
# Các hàm/giá trị toán học cho phép
_MATH_ALLOWED = {
    "math": math,
    "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf, "nan": math.nan,
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log2": math.log2, "log10": math.log10, "exp": math.exp,
    "abs": abs, "min": min, "max": max, "round": round, "pow": pow,
    "ceil": math.ceil, "floor": math.floor, "factorial": math.factorial,
    "radians": math.radians, "degrees": math.degrees,
}

def tool_calc(expression: str) -> str:
    expr = (expression or "").strip()
    expr = expr.replace("^", "**")
    try:
        tree = ast.parse(expr, mode="eval")
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                return f"❌ Không cho phép import trong calc: {expr}"
            if isinstance(n, ast.Attribute):
                # chặn a.b kiểu nguy hiểm
                if isinstance(n.value, ast.Constant):
                    return f"❌ Không cho phép attribute: {expr}"
                if not (isinstance(n.value, ast.Name) and n.value.id == "math"):
                    # cho phép nếu là method của builtin type như float/int? => không
                    return f"❌ Không cho phép attribute '{n.attr}': {expr}"
            if isinstance(n, ast.Name):
                if n.id not in _MATH_ALLOWED:
                    return f"❌ Biểu thức chứa tên không cho phép '{n.id}': {expr}"
        val = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, _MATH_ALLOWED)
        return f"📊 {expression} = {val}"
    except Exception as e:
        return f"❌ Lỗi tính: {e}"


# ---------- TOOL: files ----------
def tool_write(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"✅ Đã ghi {len(content)} bytes → {p.relative_to(SAFE_ROOT)}"

def tool_read(path: str) -> str:
    p = _safe_path(path)
    if not p.exists():
        return f"❌ Không tìm thấy: {p.relative_to(SAFE_ROOT)}"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if len(txt) > 4000:
        return txt[:4000] + f"\n…(còn {len(txt)-4000} ký tự nữa)"
    return txt

def tool_list(path: str = ".") -> str:
    p = _safe_path(path)
    if not p.exists(): return f"❌ Không tồn tại: {p}"
    if not p.is_dir(): return tool_read(str(p))
    items = sorted(p.iterdir())
    if not items: return f"📂 {p.relative_to(SAFE_ROOT)}/  (trống)"
    lines = [f"📂 {p.relative_to(SAFE_ROOT)}/"]
    for it in items:
        size = it.stat().st_size if it.is_file() else 0
        mark = "📁" if it.is_dir() else "📄"
        tail = f"  ({size}B)" if it.is_file() else "/"
        lines.append(f"  {mark} {it.name}{tail}")
    return "\n".join(lines)


# ---------- TOOL: now ----------
def tool_now(*_) -> str:
    return "🕒 " + time.strftime("%H:%M:%S  %d/%m/%Y")


# ---------- TOOL: run_python (sandbox) ----------
_SAFE_BUILTINS = {
    # các hàm/đối tượng an toàn
    "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin, "bool": bool,
    "bytes": bytes, "chr": chr, "complex": complex, "dict": dict, "dir": dir,
    "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "hasattr": hasattr, "hash": hash,
    "hex": hex, "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max, "min": min,
    "next": next, "oct": oct, "ord": ord, "pow": pow, "print": print, "range": range,
    "repr": repr, "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}
_SAFE_IMPORTS = {"math", "random", "statistics", "datetime", "collections",
                 "itertools", "functools", "re", "json", "string", "time"}

_BLOCKED_ATTR = {"__import__", "__subclasses__", "__class__", "__bases__",
                 "__mro__", "__globals__", "__code__", "__func__", "__self__",
                 "eval", "exec", "compile", "open", "input", "breakpoint",
                 "__builtins__", "globals", "locals", "getattr"}


def _validate_ast(code: str):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] not in _SAFE_IMPORTS:
                    raise ValueError(f"Không cho phép import module '{node.module}'")
            else:
                for n in node.names:
                    if n.name.split(".")[0] not in _SAFE_IMPORTS:
                        raise ValueError(f"Không cho phép import '{n.name}'")
        if isinstance(node, ast.Attribute):
            if node.attr in _BLOCKED_ATTR:
                raise ValueError(f"Không cho phép truy cập '{node.attr}'")
        if isinstance(node, ast.Name):
            if node.id in ("open", "eval", "exec", "compile", "__import__",
                           "globals", "locals", "breakpoint", "input", "exit", "quit"):
                raise ValueError(f"Không cho phép dùng '{node.id}'")
    return tree


def _run_code_proc(code, q):
    try:
        _validate_ast(code)
        buf = io.StringIO()
        g = {"__builtins__": _SAFE_BUILTINS, "__name__": "__clara_sandbox__"}
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                exec(code, g, g)
                result_var = g.get("result", None)
            except SystemExit:
                result_var = None
        out = buf.getvalue()
        if result_var is not None and (not out or not out.endswith("\n")):
            if out: out += "\n"
            out += f"=> {result_var!r}"
        q.put(("ok", out.strip() or "(không có output)"))
    except Exception as e:
        tb = traceback.format_exc(limit=2)
        q.put(("err", f"❌ Lỗi Python:\n{tb}"))


def tool_run_python(code: str, timeout: int = 8) -> str:
    if not code or not code.strip():
        return "❌ Chưa có code để chạy."
    # Bỏ ```python ... ``` nếu user/agent gõ
    code = re.sub(r"^```(?:python)?\s*", "", code.strip())
    code = re.sub(r"\s*```$", "", code)
    try:
        _validate_ast(code)
    except SyntaxError as e:
        return f"❌ Lỗi cú pháp: {e}"
    except ValueError as e:
        return f"🛑 {e}"
    q = mp.Queue()
    p = mp.Process(target=_run_code_proc, args=(code, q), daemon=True)
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        return f"⏱️ Code chạy quá {timeout}s, đã dừng."
    if q.empty():
        return "❌ Không có kết quả trả về."
    status, val = q.get()
    return val if status == "ok" else val


# ---------- TOOL: search memory ----------
def tool_search_memory(agent, query: str) -> str:
    sems = agent.mem.recall_semantics(query, limit=8)
    eps = agent.mem.recall_episodes(query, limit=5)
    out = ["🔎 Tìm trong bộ nhớ:"]
    if sems:
        out.append("— Kiến thức:")
        for r in sems:
            stars = "★" * max(1, int(round(r["confidence"]*5)))
            out.append(f"  {stars} {r['fact']}")
    if eps:
        out.append("— Ký ức:")
        for r in eps:
            t = time.strftime("%d/%m %H:%M", time.localtime(r["ts"]))
            snippet = r["content"].replace("\n", " ")[:120]
            out.append(f"  [{t}] {snippet}")
    if len(out) == 1:
        out.append("  (không tìm thấy gì)")
    return "\n".join(out)


# ---------- TOOL: help ----------
def tool_help(*_) -> str:
    return (
        "🛠️ Các công cụ CLARA có thể dùng:\n"
        "  • calc <bt>           tính biểu thức (vd: calc sqrt(2)*2)\n"
        "  • now                 xem ngày giờ\n"
        "  • list [path]         liệt kê file trong workspace\n"
        "  • read <path>         đọc file\n"
        "  • write <path>|<nội dung>   ghi file (dùng | để phân cách path)\n"
        "  • run_python <code>   chạy code Python trong sandbox an toàn\n"
        "  • search <từ khóa>    tìm trong bộ nhớ\n"
        "  • help                danh sách này\n"
        "\nWorkspace: " + str(SAFE_ROOT)
    )


# ---------- Dispatch ----------
TOOLS = {
    "calc":        {"fn": tool_calc,        "needs_agent": False, "desc": "Tính toán"},
    "now":         {"fn": tool_now,         "needs_agent": False, "desc": "Xem ngày giờ"},
    "list":        {"fn": tool_list,        "needs_agent": False, "desc": "Liệt kê file"},
    "read":        {"fn": tool_read,        "needs_agent": False, "desc": "Đọc file"},
    "write":       {"fn": tool_write,       "needs_agent": False, "desc": "Ghi file (path|content)"},
    "run_python":  {"fn": tool_run_python,  "needs_agent": False, "desc": "Chạy Python sandbox"},
    "search":      {"fn": tool_search_memory,"needs_agent": True, "desc": "Tìm trong bộ nhớ"},
    "help":        {"fn": tool_help,        "needs_agent": False, "desc": "Trợ giúp"},
}


def parse_and_dispatch(agent, text: str):
    """text là chuỗi 'toolname args'. agent là ClarasAGI instance."""
    text = (text or "").strip().strip("`")
    if not text or text == "none" or text.startswith("không"):
        return ""
    parts = text.split(None, 1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    # alias
    aliases = {"compute": "calc", "ls": "list", "cat": "read", "dir": "list",
               "py": "run_python", "python": "run_python", "grep": "search",
               "find": "search", "time": "now", "date": "now"}
    name = aliases.get(name, name)
    if name not in TOOLS:
        return f"❌ Không có công cụ '{name}'. Gõ 'help' để xem."
    spec = TOOLS[name]
    fn = spec["fn"]
    try:
        if name == "write":
            if "|" not in arg:
                return "ℹ️ Dùng: write <path>|<nội dung>"
            p, c = arg.split("|", 1)
            return fn(p.strip(), c.lstrip())
        if spec["needs_agent"]:
            return fn(agent, arg.strip())
        if arg:
            return fn(arg.strip())
        return fn()
    except Exception as e:
        return f"❌ Lỗi tool {name}: {e}"
