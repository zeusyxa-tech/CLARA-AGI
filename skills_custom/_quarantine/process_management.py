#!/usr/bin/env python3
"""
CLARA-AGI Skill: process_management
Xem tiến trình, tắt tiến trình, lấy log đơn giản.
"""
import subprocess, shlex, os
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2] / "workspace"
LOGS_DIR = WORKSPACE / ".logs"
LOGS_DIR.mkdir(exist_ok=True)


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: ps:<subcmd>|<arg>\n"
                "  list                  list .logs/*.pid\n"
                "  start:<name>|<cmd>    start background shell task\n"
                "  stop:<name>           stop by pid/name\n"
                "  log:<name>            tail log\n"
                "  ps aux                quick ps aux")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub == "list":
            files = sorted(LOGS_DIR.glob("*.pid"))
            if not files: return "(no tracked processes)"
            rows = []
            for f in files:
                pid = f.read_text(encoding="utf-8", errors="replace").strip()
                rows.append(f"{f.stem}: pid={pid}")
            return "\n".join(rows)
        if sub.startswith("start"):
            if "|" not in arg:
                return "❌ start:<name>|<cmd>"
            name, cmd = arg.split("|", 1)
            name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:24]
            pid_path = LOGS_DIR / f"{name}.pid"
            log_path = LOGS_DIR / f"{name}.log"
            p = subprocess.Popen(
                shlex.split(cmd), cwd=str(WORKSPACE),
                stdout=open(log_path, "ab+"), stderr=subprocess.STDOUT, start_new_session=True
            )
            pid_path.write_text(str(p.pid), encoding="utf-8")
            return f"▶ {name} started pid={p.pid} log={log_path.relative_to(WORKSPACE)}"
        if sub.startswith("stop"):
            target = arg.strip()
            pid_path = LOGS_DIR / f"{target}.pid"
            if not pid_path.exists():
                return f"❌ không thấy {target}.pid"
            pid = int(pid_path.read_text())
            try:
                os.kill(pid, 9)
                pid_path.unlink()
                return f"⏹ stopped {target} pid={pid}"
            except ProcessLookupError:
                pid_path.unlink()
                return "⏹ process already gone"
        if sub.startswith("log"):
            target = arg.strip()
            log_path = LOGS_DIR / f"{target}.log"
            if not log_path.exists():
                return f"❌ không thấy {target}.log"
            data = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            tail = data[-200:]
            return "\n".join(tail) or "(empty log)"
        if sub == "ps aux":
            out = subprocess.check_output(["ps", "aux"], text=True)
            return "\n".join(out.splitlines()[:80])
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
