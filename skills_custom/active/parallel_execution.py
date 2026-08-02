#!/usr/bin/env python3
"""
CLARA-AGI Skill: parallel_execution
Chạy nhiều biểu thức Python song song trong sandbox process.
Cú pháp: parallel:<expr>;<expr>;...
"""
import multiprocessing as mp
import io, contextlib, traceback
from tools import _validate_ast, _SAFE_BUILTINS


def _run_expr(expr, q):
    try:
        _validate_ast(expr)
        buf = io.StringIO()
        g = {"__builtins__": _SAFE_BUILTINS, "__name__": "__parallel__"}
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(expr, g, g)
        q.put(("ok", buf.getvalue().strip() or "(empty)"))
    except Exception as e:
        q.put(("err", f"❌ {e}"))


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return "Usage: parallel:<expr>|<expr2>|<expr3>\nOutput parallel tính toán, print==result."
    exprs = text.split("|", 1)[1].split("|")
    exprs = [e.strip() for e in exprs if e.strip()]
    if not exprs:
        return exprs
    if len(exprs) > 6:
        exprs = exprs[:6]
    qs = []
    ps = []
    for expr in exprs:
        q = mp.Queue()
        p = mp.Process(target=_run_expr, args=(expr, q), daemon=True)
        ps.append((p, q))
        p.start()
    results = []
    for p, q in ps:
        p.join(timeout=12)
        if p.is_alive():
            p.terminate()
            p.join(1)
            results.append("⏱️ timeout")
        elif q.empty():
            results.append("(no output)")
        else:
            st, msg = q.get()
            results.append(msg if st == "ok" else msg)
    return "\n".join(f"{i+1}) {r}" for i, r in enumerate(results))
