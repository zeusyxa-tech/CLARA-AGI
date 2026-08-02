#!/usr/bin/env python3
"""
CLARA-AGI Skill: math_computation
Toán nâng cao: stats, equation solve approximation, matrix, complex.
"""
import math
import random


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: math:<subcmd>|<args>\n"
                "  stats:<comma-sep numbers>   mean,median,std,min,max\n"
                "  solve:<expr>|<initial>       newton-step approximation\n"
                "  matrix:<csv>                 forme A\n"
                "  complex:<op>|<a>|<b>         + - * / abs,arg")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    payload = parts[1] if len(parts) > 1 else ""
    try:
        if sub == "stats":
            nums = [float(x.strip()) for x in payload.split(",") if x.strip()]
            if not nums:
                return "❌ stats cần >=1 số, phân tách bằng ,"
            n = len(nums)
            s = sum(nums)
            mean = s / n
            nums2 = sorted(nums)
            median = (nums2[n//2] if n%2 else (nums2[n//2-1]+nums2[n//2])/2)
            variance = sum((x-mean)**2 for x in nums)/max(n-1,1)
            return f"n={n} sum={s:.4g} mean={mean:.4g} median={median:.4g} std={math.sqrt(variance):.4g} min={min(nums)} max={max(nums)}"
        if sub == "solve":
            expr, x0_s = payload.split("|", 1) if "|" in payload else (payload, "1")
            x0 = float(x0_s.strip())
            def f(x): return eval(expr, {"__builtins__": {}, "x": x, "math": math, "sin": math.sin, "cos": math.cos, "exp": math.exp, "log": math.log, "sqrt": math.sqrt})
            def fprime(x):
                h = 1e-6
                return (f(x+h)-f(x-h))/(2*h)
            x = x0
            for _ in range(20):
                fx, fp = f(x), fprime(x)
                if fp == 0: break
                x = x - fx/fp
                if abs(fx) < 1e-9:
                    break
            return f"≈ root {x:.8g}  f={f(x):.3e}"
        if sub == "matrix":
            rows = [list(map(float, r.strip().split())) for r in payload.strip().splitlines() if r.strip()]
            if not rows: return "❌ matrix cần CSV"
            cols = max(len(r) for r in rows)
            rows = [r + [0]*(cols-len(r)) for r in rows]
            sums = [sum(row[j] for row in rows) for j in range(cols)]
            avgs = [s/len(rows) for s in sums]
            det = None
            if len(rows) == len(cols) == 2:
                a,b,c,d = rows[0][0],rows[0][1],rows[1][0],rows[1][1]
                det = a*d - b*c
            out = [f"shape={len(rows)}x{cols}", f"col_sums={[round(x,4) for x in sums]}", f"col_avgs={[round(x,4) for x in avgs]}"]
            if det is not None: out.append(f"det={det}")
            out.append("matrix_rows:\n" + "\n".join("  " + " ".join(f"{v:.4g}" for v in r) for r in rows))
            return "\n".join(out)
        if sub == "complex":
            args = payload.split("|")
            op = args[0].strip() if args else "+"
            a = complex(args[1].strip()) if len(args)>1 else 0+0j
            b = complex(args[2].strip()) if len(args)>2 else 0+0j
            if op == "+": r = a + b
            elif op == "-": r = a - b
            elif op == "*": r = a * b
            elif op == "/": r = a / b
            else: return "❌ op: + - * /"
            if op in ("abs",): r = abs(a)
            if op in ("arg",): r = math.degrees(math.atan2(a.imag, a.real))
            return f"{a} {op} {b} = {r}"
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
