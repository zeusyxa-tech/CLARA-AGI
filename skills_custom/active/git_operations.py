#!/usr/bin/env python3
"""
CLARA-AGI Skill: git_operations
Git wrapper đọc-only + safe commit branch ops.
"""
import subprocess, shlex
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2] / "workspace"


def _run(args):
    r = subprocess.run(args, cwd=str(WORKSPACE), capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def run(agi, text: str) -> str:
    text = text.strip()
    if not text:
        return "Usage: git <status|log|diff|branch|current|ls-files> [args]"
    parts = text.split()
    cmd = parts[0]
    limit = parts[1] if len(parts) > 1 and parts[1].isdigit() else "20"
    if cmd in ("status", "--short"):
        out, err, rc = _run(["git", "status", "--short", "-b"])
        return out or "(clean)\n\n" + err if err else out or "(clean)"
    if cmd == "log":
        out, _, _ = _run(["git", "log", f"--oneline", f"-n", limit])
        return out or "(no history)"
    if cmd == "diff":
        out, _, _ = _run(["git", "diff", "--stat", f"-n", limit])
        return out or "(no diff)"
    if cmd in ("branch", "branches"):
        out, _, _ = _run(["git", "branch", "-a"])
        return out or "(no branches)"
    if cmd == "current":
        out, _, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return out
    if cmd == "ls-files":
        out, _, _ = _run(["git", "ls-files"])
        return "\n".join(out.splitlines()[:50]) or "(empty)"
    return f"❌ Unknown git cmd: {cmd}. status|log|diff|branch|current|ls-files"
