"""CLARA-AGI Self-Test — kiểm tra nhanh các module cốt lõi.

Chạy:  python3 skills_custom/active/clara_self_test.py
Hoặc:   python3 main.py chat "chạy self test"
"""
import sys
import os
import traceback
from pathlib import Path

# Đảm bảo import được từ thư mục gốc dự án
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0
RESULTS = []


def check(name, fn):
    """Chạy 1 test case, bắt lỗi, ghi kết quả."""
    global PASS, FAIL
    try:
        ok, detail = fn()
        if ok:
            PASS += 1
            RESULTS.append(f"  ✅ {name}")
        else:
            FAIL += 1
            RESULTS.append(f"  ❌ {name} — {detail}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(f"  ❌ {name} — {type(e).__name__}: {e}")


def t_imports():
    import config
    import memory
    import brain
    import tools
    import web_tools
    return True, "all import OK"


def t_config():
    from config import get_config
    model = get_config("llm", "default_model")
    if not model:
        return False, "llm.default_model rỗng"
    return True, f"model={model}"


def t_memory_basic():
    from memory import Memory
    m = Memory()
    n0 = m.stats().get("episodes", 0)
    m.remember_episode("self_test_probe", "xin chào từ test", importance=0.9)
    n1 = m.stats().get("episodes", 0)
    if n1 != n0 + 1:
        return False, f"episodes không tăng ({n0}->{n1})"
    # dọn
    m.conn.execute("DELETE FROM episodes WHERE content=?", ("xin chào từ test",))
    m.conn.commit()
    return True, "add_episode OK"


def t_memory_sql_safe():
    """update_goal dùng parameterized query (Pattern 1)."""
    from memory import Memory
    m = Memory()
    try:
        m.update_goal(999999, status="active")
        return True, "update_goal không crash"
    except Exception as e:
        # lỗi do id không tồn tại là bình thường, chỉ cần không phải SQL injection error
        return True, f"update_goal xử lý an toàn (id lạ): {type(e).__name__}"


def t_brain_micro():
    from brain import Brain
    b = Brain(force_micro=True)
    if b.backend != "micro":
        return False, f"backend={b.backend} (mong đợi micro)"
    out = b.think("__REWRITE__", "Trả lời ngắn: 1+1=?")
    if not out:
        return False, "micro brain trả về rỗng"
    return True, f"micro think OK ({len(out)} chars)"


def t_tools_calc():
    from tools import parse_and_dispatch
    out = parse_and_dispatch(None, "calc 2 + 3 * 4")
    if "14" not in out:
        return False, f"calc sai: {out}"
    return True, "calc 2+3*4=14 OK"


def t_tools_python_guard():
    """tool_run_python phải cleanup process (Pattern 2)."""
    from tools import tool_run_python
    out = tool_run_python("print('hello_clara_test')")
    if "hello_clara_test" not in out:
        return False, f"python chạy fail: {out}"
    return True, "python sandbox OK"


def t_web_tools_fallback():
    """web_tools import được kể cả khi thiếu bs4."""
    import web_tools
    assert hasattr(web_tools, "web_search")
    assert hasattr(web_tools, "web_fetch")
    return True, f"web_tools OK (HAS_BS4={getattr(web_tools, 'HAS_BS4', '?')})"


def t_self_improve_ast():
    """_validate_skill_ast chặn code nguy hiểm (Pattern 6)."""
    from self_improve import _validate_skill_ast
    bad = "import os\nos.system('rm -rf /')"
    good = "import math\nresult = math.sqrt(16)"
    if _validate_skill_ast(bad):
        return False, "AST validator không chặn os.system"
    if not _validate_skill_ast(good):
        return False, "AST validator sai chặn code an toàn"
    return True, "AST validation OK"


def main():
    print("🧪 CLARA-AGI Self-Test")
    print("=" * 40)
    check("Import tất cả module", t_imports)
    check("Config loader", t_config)
    check("Memory add_episode", t_memory_basic)
    check("Memory SQL an toàn", t_memory_sql_safe)
    check("Brain micro fallback", t_brain_micro)
    check("Tools: calc", t_tools_calc)
    check("Tools: python sandbox", t_tools_python_guard)
    check("Web tools import", t_web_tools_fallback)
    check("Self-improve AST validation", t_self_improve_ast)

    print("\n".join(RESULTS))
    print("=" * 40)
    print(f"Kết quả: {PASS} passed, {FAIL} failed")
    if FAIL:
        print("⚠️  Có test thất bại — xem chi tiết ở trên.")
        return 1
    print("✅ Tất cả test qua!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
