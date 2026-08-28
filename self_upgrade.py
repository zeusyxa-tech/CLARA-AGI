"""
CLARA-AGI v1.5 - Self-Upgrade Engine (tự nâng cấp chính mình).

Đây là "hệ thần kinh" để CLARA tự sửa/thay đổi code của chính nó một cách AN TOÀN:
  - Mở rộng self_patcher: được phép vá CẢ LÕI (brain.py, agent.py, main.py,
    config.py, memory.py, tools.py, web_tools.py, autolearn.py, scheduler.py,
    self_improve.py, self_improve_loop.py, voice.py, webui.py).
  - Mỗi lần upgrade: snapshot git (checkpoint) -> đề xuất patch bằng LLM ->
    backup file -> áp dụng -> smoke-test (py_compile + import) -> nếu fail thì
    rollback tự động về backup, còn thành công mới giữ (và ghi log upgrade).
  - Tự động chạy định kỳ (khi rảnh) để rà soát lỗi và đề xuất nâng cấp.

Mọi thay đổi đều có thể rollback bằng `upgrade rollback <file>` hoặc
`patch rollback <file>` (từ self_patcher).
"""
import ast
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

BASE = Path(__file__).parent

# ---- Các file được phép tự vá (mở rộng so với self_patcher cũ) ----
# Loại trừ duy nhất: chính module này + file binary/secret.
SAFE_FILES = {
    "tools.py", "memory.py", "web_tools.py", "autolearn.py",
    "scheduler.py", "self_improve.py", "self_improve_loop.py",
    "voice.py", "webui.py", "config.py", "brain.py", "agent.py",
    "main.py", "embeddings.py", "logging_utils.py", "compliance.py",
    "curriculum.py", "code_curriculum.py",
}
ALLOWED_DIRS = {BASE / "skills_custom"}
BACKUP_SUFFIX = ".bak"

# Đánh giá rủi ro: file càng lõi càng cần thận trọng
CORE_FILES = {"brain.py", "agent.py", "main.py", "config.py", "memory.py"}


def _is_allowed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(BASE.resolve())
    except ValueError:
        return False
    if rel.parts[0] == "skills_custom":
        return path.suffix == ".py"
    return rel.name in SAFE_FILES


def _backup(path: Path):
    bkp = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    shutil.copy2(path, bkp)
    return bkp


def _validate_syntax(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        return True
    except Exception:
        return False


def _git_available() -> bool:
    return (BASE / ".git").is_dir()


def _git_checkpoint(label: str) -> str:
    """Tạo checkpoint git (commit working tree) để rollback an toàn ở mức repo."""
    if not _git_available():
        return "(no-git)"
    try:
        subprocess.run(["git", "add", "-A"], cwd=BASE, capture_output=True, timeout=30)
        r = subprocess.run(
            ["git", "commit", "-m", f"auto-checkpoint: {label}"],
            cwd=BASE, capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "committed"
        # nothing to commit
        return "(clean)"
    except Exception as e:
        return f"(git-err: {e})"


def propose_upgrade(agi, filename: str, instruction: str) -> dict:
    """
    Đề xuất + áp dụng một nâng cấp an toàn cho file của CLARA.
    `instruction` là mô tả yêu cầu; LLM sinh patch (SEARCH/REPLACE).
    Trả về dict: ok, error, file, backup, diff_summary, git, smoke.
    """
    target = (BASE / filename).resolve()
    if not _is_allowed(target):
        return {"ok": False, "error": f"File '{filename}' nằm ngoài danh sách cho phép tự vá."}
    if not target.exists():
        return {"ok": False, "error": f"File '{filename}' không tồn tại."}

    is_core = target.name in CORE_FILES
    current = target.read_text(encoding="utf-8")

    prompt = (
        "Bạn là module SELF-UPGRADE của CLARA-AGI. Hãy đề xuất một bản vá (patch) "
        "cho file Python sau nhằm cải thiện nó.\n"
        "Ràng buộc nghiêm ngặt:\n"
        "1. CHỈ sửa nội dung file, không đổi tên, không xóa import/định nghĩa công khai.\n"
        "2. Phải giữ nguyên tất cả API/hàm/class hiện có (chỉ thêm/sửa thân hàm).\n"
        "3. Không dùng eval/exec/os.system/subprocess ngoài mục đích rõ ràng & an toàn.\n"
        "4. Trả về DUY NHẤT một block:\n"
        "   SEARCH:\n<đoạn cũ chính xác, nguyên văn>\n   REPLACE:\n<đoạn mới>\n"
        "5. Nếu không chắc, trả về 'NO_CHANGE'.\n"
        f"Tên file: {filename} (lõi={'có' if is_core else 'không'})\n"
        f"Yêu cầu: {instruction}\n"
        "=== FILE CONTENT ===\n"
        f"{current[:14000]}\n=== END FILE ==="
    )
    raw = agi.brain.think("__ANSWER__", prompt, temperature=0.2, num_predict=1500)
    if "NO_CHANGE" in raw:
        return {"ok": False, "error": "Model đề xuất không thay đổi.", "raw": raw}

    m = re.search(r"SEARCH:\s*(.*?)\s*REPLACE:\s*(.*)", raw, re.S)
    if not m:
        return {"ok": False, "error": "Không parse được patch.", "raw": raw}

    old_snippet = m.group(1).strip()
    new_snippet = m.group(2).strip()
    return apply_patch(filename, old_snippet, new_snippet, is_core=is_core)


def apply_patch(filename: str, old_snippet: str, new_snippet: str, is_core: bool = False,
                agi=None) -> dict:
    """
    Áp dụng một patch (SEARCH/REPLACE) đã parse sẵn vào file — có git checkpoint,
    backup, kiểm tra cú pháp, smoke-test import và rollback tự động khi fail.
    Có thể gọi trực tiếp (bypass LLM) để test pipeline an toàn.
    """
    target = (BASE / filename).resolve()
    if not _is_allowed(target):
        return {"ok": False, "error": f"File '{filename}' nằm ngoài danh sách cho phép tự vá."}
    if not target.exists():
        return {"ok": False, "error": f"File '{filename}' không tồn tại."}
    current = target.read_text(encoding="utf-8")
    if old_snippet not in current:
        return {"ok": False, "error": "Đoạn SEARCH không khớp file hiện tại."}

    # git checkpoint trước khi đụng
    git_ref = _git_checkpoint(f"before-upgrade {filename}")

    backup = _backup(target)
    try:
        new_content = current.replace(old_snippet, new_snippet, 1)
        target.write_text(new_content, encoding="utf-8")
        if not _validate_syntax(target):
            shutil.copy2(backup, target)
            return {"ok": False, "error": "Patch gây lỗi cú pháp, đã rollback.",
                    "backup": str(backup), "git": git_ref}
        # smoke-test import
        smoke = _smoke_import(target)
        if not smoke["ok"]:
            shutil.copy2(backup, target)
            return {"ok": False, "error": "Import lỗi sau patch, đã rollback: " + smoke["error"],
                    "backup": str(backup), "git": git_ref}
        return {
            "ok": True,
            "file": str(target),
            "backup": str(backup),
            "git": git_ref,
            "diff_summary": f"Đã thay {len(old_snippet)} → {len(new_snippet)} bytes",
            "is_core": is_core,
            "smoke": "ok",
        }
    except Exception as e:
        if backup.exists():
            shutil.copy2(backup, target)
        return {"ok": False, "error": str(e), "backup": str(backup), "git": git_ref}


def _smoke_import(target: Path) -> dict:
    """Import module trong namespace tạm để bắt lỗi import/side-effect."""
    mod_name = f"__clara_upg_{target.stem}__"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(mod_name, str(target))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {"ok": True, "exports": [a for a in dir(mod) if not a.startswith("_")][:15]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def scan_for_issues(agi) -> list:
    """
    Tự rà soát các file lõi để tìm điểm yếu (regex heuristic + LLM đánh giá nhẹ).
    Trả về list các dict: {file, issue, severity}.
    """
    issues = []
    # Heuristic: hàm quá dài, except bare, print thay vì log, TODO cứng
    patterns = {
        r"except\s*:\s*$": ("bare-except", "medium"),
        r"print\(": ("dùng print thay log", "low"),
        r"TODO|FIXME|XXX": ("còn việc chưa làm", "low"),
    }
    for f in SAFE_FILES:
        p = BASE / f
        if not p.exists():
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            for pat, (label, sev) in patterns.items():
                if re.search(pat, ln):
                    issues.append({"file": f, "line": i, "issue": label, "severity": sev})
                    break
    return issues


def list_backups():
    return [p.name for p in BASE.glob(f"*{BACKUP_SUFFIX}") if p.is_file()]


def rollback(filename: str) -> str:
    target = BASE / filename
    bkp = target.with_suffix(target.suffix + BACKUP_SUFFIX)
    if not bkp.exists():
        return f"❌ Không có backup cho '{filename}'."
    shutil.copy2(bkp, target)
    return f"♻️ Đã rollback '{filename}' về bản backup."


class SelfUpgradeLoop:
    """Chạy nền: định kỳ rà soát và tự upgrade nhẹ nhàng."""

    def __init__(self, agi, interval=600, verbose=True):
        self.agi = agi
        self.interval = interval
        self.verbose = verbose
        self._running = False
        self._thread = None
        self.steps_done = 0
        self.stats = {"scans": 0, "upgrades_ok": 0, "upgrades_fail": 0}

    def start(self):
        if self._running:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        return True

    def status(self):
        return {"running": self._running, "interval": self.interval,
                "steps_done": self.steps_done, "stats": self.stats}

    def _loop(self):
        time.sleep(20)
        while self._running:
            try:
                self._one_step()
            except Exception as e:
                if self.verbose:
                    print(f"[self-upgrade] err: {e}", flush=True)
            for _ in range(int(self.interval)):
                if not self._running:
                    return
                time.sleep(1)

    def _log(self, msg):
        if self.verbose:
            t = time.strftime("%H:%M:%S")
            print(f"\r🔧 [{t}] self-upgrade: {msg}", flush=True)

    def _one_step(self):
        self.steps_done += 1
        self.stats["scans"] += 1
        issues = scan_for_issues(self.agi)
        # Chỉ tự vá những issue mức medium (bare-except) để an toàn; low thì bỏ qua.
        targets = [x for x in issues if x["severity"] == "medium"]
        if not targets:
            self._log("quét sạch, chưa cần nâng cấp.")
            return
        t = targets[0]
        instr = (
            f"Trong {t['file']} dòng {t['line']} có '{t['issue']}'. "
            f"Hãy sửa thành cách an toàn (ví dụ bắt Exception cụ thể) "
            f"mà không đổi behaviour bên ngoài."
        )
        self._log(f"tự vá: {t['file']}:{t['line']} ({t['issue']})")
        res = propose_upgrade(self.agi, t["file"], instr)
        if res.get("ok"):
            self.stats["upgrades_ok"] += 1
            self._log(f"✅ upgrade thành công: {t['file']} [{res.get('git')}]")
            self.agi.mem.remember_episode(
                "self_upgrade",
                f"Tự nâng cấp {t['file']}: {t['issue']} → {res.get('diff_summary')}",
                importance=0.8, emotion=0.3)
        else:
            self.stats["upgrades_fail"] += 1
            self._log(f"⚠️ upgrade fail: {res.get('error','')[:80]}")
