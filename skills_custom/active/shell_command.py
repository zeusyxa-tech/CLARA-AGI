#!/usr/bin/env python3
"""
CLARA-AGI Skill: shell_command (safe)
Chạy shell command trong workspace với whitelist + no shell=True.
"""
import subprocess
import shlex
from pathlib import Path
from tools import SAFE_ROOT

ALLOWED_CMDS = {
    "echo", "pwd", "ls", "cat", "head", "tail", "grep", "wc",
    "date", "whoami", "hostname", "python3", "pip", "git",
    "touch", "mkdir", "rm", "cp", "mv", "diff",
    "curl", "wget", "jq", "sed", "awk",
}


def run(agi, text: str) -> str:
    text = text.strip()
    if not text:
        return "Usage: shell:<command>. Example: shell:ls -la\nWhitelist: " + ", ".join(sorted(ALLOWED_CMDS))
    try:
        tokens = shlex.split(text)
        if not tokens:
            return ""
        cmd0 = tokens[0]
        if cmd0 not in ALLOWED_CMDS:
            return f"❌ '{cmd0}' không trong whitelist: {sorted(ALLOWED_CMDS)}"
        # Block destructive flags noisily
        blocked = {"rm -rf", "rm -fr", "rmdir /s"}
        if any(text.startswith(b) for b in blocked):
            return "❌ Lệnh hủy bỏ. Dùng rm <file> để xóa an toàn từng file trong workspace."
        env = {**__import__('os').environ, "PWD": str(SAFE_ROOT)}
        r = subprocess.run(
            tokens,
            cwd=str(SAFE_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        if r.returncode != 0 and err:
            out = out + "\n" + err if out else err
        return out if out else "(empty output)"
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout 30s"
    except Exception as e:
        return f"❌ {e}"
