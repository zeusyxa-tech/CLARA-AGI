"""
CLARA-AGI v1.5 - Công cụ (tools) — tay chân của agent.
- calc: tính toán an toàn
- read_file / write_file / list_files: thao tác file trong workspace
- now: ngày giờ
- run_python: chạy code Python trong sandbox (AST-based filter + timeout + giới hạn tài nguyên)
- search_memory: tìm trực tiếp trong bộ nhớ
- shell: *chỉ khi người dùng bật chế độ không an toàn*
"""
import ast
import re
import json
import math
import os
import sys
import time
import io
import contextlib
import traceback
import resource
import subprocess
import tempfile
from pathlib import Path

SAFE_ROOT = (Path(__file__).parent / "workspace").resolve()
SAFE_ROOT.mkdir(exist_ok=True)

try:
    from vision import tool_vision
except Exception:
    tool_vision = None

# ---------- MATH HELPER ----------
_ALLOWED_NAMES = {
    k: v for k, v in math.__dict__.items() if not k.startswith("__")
}
_ALLOWED_NAMES.update({
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "pow": pow,
    "len": len,
    "True": True,
    "False": False,
    "None": None,
})


def tool_calc(expr: str) -> str:
    expr = expr.strip()
    if not expr:
        return "❌ Thiếu biểu thức."
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return f"❌ Lỗi cú pháp: {e}"
    # Only allow Num/BinOp/UnaryOp/Call(no attrs)/Name/Constant
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.Load,
                             ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                             ast.Pow, ast.FloorDiv, ast.USub, ast.UAdd,
                             ast.operator, ast.unaryop, ast.expr_context)):
            continue
        return "❌ Biểu thức chứa toán tử/phép toán không cho phép."
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_NAMES:
                continue
            if isinstance(node.func, ast.Attribute):
                return "❌ Không cho phép gọi thuộc tính (dùng '.')."
            return "❌ Chỉ cho phép gọi hàm an toàn."
    try:
        val = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}, **_ALLOWED_NAMES})
    except Exception as e:
        return f"❌ Lỗi tính toán: {e}"
    return f"📊 {expr} = {val}"


# ---------- SAFE FS ----------
def _safe_path(path: str) -> Path:
    if not path:
        return SAFE_ROOT
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = SAFE_ROOT / p
    try:
        p.resolve().relative_to(SAFE_ROOT.resolve())
    except Exception:
        return SAFE_ROOT / "safe-mapped.txt"
    return p


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
    if not p.exists():
        return f"❌ Không tồn tại: {p}"
    if not p.is_dir():
        return tool_read(str(p))
    items = sorted(p.iterdir())
    if not items:
        return f"📂 {p.relative_to(SAFE_ROOT)}/  (trống)"
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


def tool_list_skills(agent, *_) -> str:
    try:
        from self_improve import list_pending, list_active
        pending = list_pending()
        active = list_active()
        out = [f"🧩 Skills active: {len(active)}"]
        for it in active:
            out.append(f"  • {it['file']}")
        out.append(f"⏳ Skills pending: {len(pending)}")
        for it in pending:
            out.append(f"  • {it['file']}")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Lỗi liệt kê skills: {e}"


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
        "  • vision <path>       phân tích ảnh (dùng | để thêm câu hỏi)\n"
        "  • help                danh sách này\n"
        "\nWorkspace: " + str(SAFE_ROOT)
    )


# ---------- Global sandbox policy ----------
_DANGEROUS_PYTHON = False


def _set_dangerous_python(enabled: bool):
    global _DANGEROUS_PYTHON
    _DANGEROUS_PYTHON = bool(enabled)
    if _DANGEROUS_PYTHON:
        print("⚠️  run_python đang BẬT — chỉ chạy code bạn tin cậy.")


# ---------- SANDBOXED PYTHON RUNNER ----------
_CHILD_SCRIPT = """
import sys, os, resource, traceback, unicodedata, io, contextlib, time
for lim, val in ((resource.RLIMIT_CPU,(10,10)), (resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))):
    try: resource.setrlimit(lim, val)
    except Exception: pass
try: resource.setrlimit(resource.RLIMIT_NPROC,(0,0))
except Exception: pass
safe_builtins = {
    'abs': abs, 'all': all, 'any': any, 'ascii': ascii, 'bin': bin, 'bool': bool,
    'bytes': bytes, 'chr': chr, 'complex': complex, 'dict': dict,
    'divmod': divmod, 'enumerate': enumerate, 'filter': filter, 'float': float,
    'format': format, 'frozenset': frozenset, 'hasattr': hasattr, 'hash': hash,
    'hex': hex, 'int': int, 'iter': iter, 'len': len, 'list': list, 'map': map,
    'max': max, 'min': min, 'next': next, 'oct': oct, 'ord': ord, 'pow': pow,
    'print': print, 'range': range, 'repr': repr, 'reversed': reversed,
    'round': round, 'set': set, 'slice': slice, 'sorted': sorted, 'str': str,
    'sum': sum, 'tuple': tuple, 'zip': zip, 'True': True, 'False': False, 'None': None,
}
_SAFE_IMPORTS = {"math","random","statistics","datetime","collections","itertools","functools","re","json","string","time","sys","unicodedata","traceback"}

def _resolve_import(module):
    top = module.split(".")[0]
    if top not in _SAFE_IMPORTS:
        raise ImportError("Không cho phép import module '%s'" % top)
    return __import__(module, fromlist=[module])

class SafeImporter:
    def find_module(self, fullname, path=None):
        return None
    def load_module(self, fullname):
        raise ImportError('disabled')

sys.meta_path.insert(0, SafeImporter())
g = {'__builtins__': safe_builtins, '__name__': '__clara_sandbox__', '__import__': _resolve_import}
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            exec(sys.stdin.read(), g, g)
            result_var = g.get('result', None)
        except SystemExit:
            result_var = None
    out = buf.getvalue()
    if result_var is not None and (not out or not out.endswith('\\n')):
        if out:
            out += '\\n'
        out += '=> %r' % result_var
    sys.stdout.write(out.strip() or '(không có output)')
except Exception as e:
    try:
        tb = traceback.format_exc(limit=2)
    except Exception:
        tb = '❌ Lỗi Python:\\n' + str(e)
    sys.stdout.write('❌ Lỗi Python:\\n' + tb)
"""

# ---------- AST validator ----------
_BANNED_NAMES = {"open","eval","exec","compile","__import__","globals","locals","breakpoint","input","exit","quit","type","isinstance","issubclass","dir"}
_BANNED_ATTR_PREFIXES = ("__",)
_SAFE_IMPORTS = {"math","random","statistics","datetime","collections","itertools","functools","re","json","string","time","sys","unicodedata","traceback"}


def _validate_ast(code: str) -> str:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise SyntaxError(f"Lỗi cú pháp: {e}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError(f"Không cho phép truy cập attribute bắt đầu bằng '__'.")
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda)):
            raise ValueError(f"Không cho phép định nghĩa class/async function/lambda.")
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise ValueError(f"Không cho phép dùng '{node.id}'.")
        if isinstance(node, ast.ImportFrom):
            for alias in node.names or []:
                name = alias.name
                if name == "*":
                    raise ValueError("Không cho phép 'from x import *'.")
                if any(name.startswith(prefix) for prefix in _BANNED_ATTR_PREFIXES):
                    raise ValueError(f"Không cho phép import '{name}'.")
            if node.module and node.module.startswith("__"):
                raise ValueError(f"Không cho phép import '{node.module}'.")
        if isinstance(node, ast.Import):
            for alias in node.names or []:
                top = alias.name.split(".")[0]
                if top not in _SAFE_IMPORTS:
                    raise ValueError(f"Không cho phép import module '{top}'.")
    return "ok"


def tool_run_python(code: str, timeout: int = 8) -> str:
    if not _DANGEROUS_PYTHON:
        return "❌ Công cụ 'run_python' đang TẮT (bật bằng --dangerous-python)."
    if not code or not code.strip():
        return "❌ Chưa có code để chạy."
    code = re.sub(r"^```(?:python)?\s*", "", code.strip())
    code = re.sub(r"\s*```$", "", code)
    try:
        _validate_ast(code)
    except SyntaxError as e:
        return f"❌ Lỗi cú pháp: {e}"
    except ValueError as e:
        return f"🛑 {e}"
    try:
        script_path = Path(__file__).with_name("tools_sandbox.py")
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return f"⏱️ Code chạy quá {timeout}s, đã dừng."
    except Exception as e:
        return f"❌ Không chạy được sandbox: {e}"
    out = (proc.stdout or proc.stderr or "").strip()
    if not out:
        return "❌ Không có kết quả trả về."
    return out


# ---------- COMMAND DISPATCH ----------
def _eval_calc_expression(text: str):
    expr = text.strip()
    try:
        tree = ast.parse(expr, mode="eval")
    except Exception:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                             ast.Constant, ast.Name, ast.Call, ast.Load,
                             ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                             ast.Pow, ast.FloorDiv, ast.USub, ast.UAdd,
                             ast.operator, ast.unaryop, ast.expr_context)):
            continue
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_NAMES:
                continue
            return None
    try:
        return eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}, **_ALLOWED_NAMES})
    except Exception:
        return None


def parse_and_dispatch(agent, text: str) -> str:
    raw = text.strip()
    low = raw.lower()
    # calc shortcuts
    calc_prefixes = ("calc ", "tính ", "tính:", "tính ")
    if any(low.startswith(p) for p in calc_prefixes):
        expr = raw.split(" ", 1)[1] if " " in raw else raw
        val = _eval_calc_expression(expr)
        if val is not None:
            return f"📊 {expr} = {val}"
        return f"📊 {expr} = ? (không đánh giá được)"
    if low.startswith("now "):
        return tool_now()
    if low.startswith("now:"):
        return tool_now()
    # tool dispatcher
    try:
        tool_name, _, arg = raw.partition(" ")
    except Exception:
        return "❌ Không hiểu lệnh. Gõ 'help' để xem danh sách."
    tool_name = tool_name.lower()
    mapping = {
        "help": tool_help,
        "now": tool_now,
        "read": lambda a: tool_read(a) if isinstance(a, str) else tool_read(str(a)),
        "write": lambda a: tool_write(*a.split("|", 1)) if isinstance(a, str) and "|" in a else "❌ write cần dạng path|nội_dung",
        "list": tool_list,
        "ls": tool_list,
        "search": lambda a: tool_search_memory(agent, a),
        "run_python": lambda a: tool_run_python(a),
        "py": lambda a: tool_run_python(a),
        "python": lambda a: tool_run_python(a),
    }
    if tool_name in mapping:
        if tool_name in ("run_python", "py", "python"):
            return mapping[tool_name](arg)
        if tool_name == "write":
            return mapping[tool_name](arg)
        return mapping[tool_name](arg)
    # shell fallback: explicitly opt-in via env
    if low.startswith("shell:") and os.environ.get("CLARA_ALLOW_SHELL") == "1":
        return "⚠️ Shell đã tắt theo cấu hình an toàn."
    return f"❌ Không có công cụ '{tool_name}'. Gõ 'help' để xem danh sách."


def register_tools(agi):
    TOOLS = {
        "calc": {"fn": lambda a: tool_calc(a), "needs_agent": False, "desc": "Tính toán biểu thức"},
        "now": {"fn": lambda a: tool_now(), "needs_agent": False, "desc": "Ngày giờ"},
        "read": {"fn": lambda a, b: tool_read(a), "needs_agent": False, "desc": "Đọc file"},
        "write": {"fn": lambda a, b: tool_write(a, b), "needs_agent": False, "desc": "Ghi file"},
        "list": {"fn": lambda a, b: tool_list(a), "needs_agent": False, "desc": "Liệt kê file"},
        "search": {"fn": lambda a, b: tool_search_memory(agi, a), "needs_agent": True, "desc": "Tìm trong bộ nhớ"},
        "vision": {"fn": lambda a, b: tool_vision(a, b) if tool_vision else "❌ Vision chưa cài", "needs_agent": False, "desc": "Phân tích ảnh"},
    }
    if _DANGEROUS_PYTHON:
        TOOLS["run_python"] = {"fn": lambda a, b: tool_run_python(b), "needs_agent": False, "desc": "Chạy Python sandbox"}
    return TOOLS
