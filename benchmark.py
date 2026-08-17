"""
CLARA-AGI Phase 2 - Offline-ish benchmark runner for an already-installed model.
Runs 3 short Vietnamese prompts, measures best-effort latency, and writes a JSON report.
Does not download models.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from brain import T_ANSWER, Brain

REPORT_DIR = Path(__file__).resolve().parent / "data" / "benchmarks"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


PROMPTS = [
    "Mình là sinh viên CNTT muốn học Python hiệu quả. Hãy đưa ra 3 bước thực tế trong 30 ngày.",
    "Tóm tắt ngắn gọn: spaced repetition là gì và áp dụng thế nào cho học code?",
    "Viết kế hoạch 4 bước để tạo một tool chat đơn giản bằng Python.",
]


def _peak_rss() -> int | None:
    try:
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:
        return None


def run_benchmark(model: str, backend: str = "ollama") -> dict:
    brain = Brain(force_micro=(backend != "ollama"), model=model)
    results = []
    for prompt in PROMPTS:
        t0 = time.perf_counter()
        try:
            out = brain.think(
                T_ANSWER,
                "Trả lời ngắn gọn bằng tiếng Việt, 2-4 câu.\n" + prompt,
                temperature=0.3,
                num_predict=192,
            )
            ok = bool(out and len(out.strip()) > 2)
            err = None
        except Exception as e:
            out = ""
            ok = False
            err = str(e)
        dt = time.perf_counter() - t0
        results.append({
            "prompt": prompt,
            "ok": ok,
            "elapsed_sec": round(dt, 3),
            "output_chars": len(out or ""),
            "error": err,
        })
        if not ok and backend == "ollama":
            break
    report = {
        "model": model,
        "backend": brain.backend,
        "provider_model": brain.model,
        "results": results,
        "peak_rss_bytes": _peak_rss(),
        "recommendation": "keep" if all(r["ok"] for r in results) else "downgrade_or_check_setup",
    }
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"benchmark_{model.replace(':','_')}_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
