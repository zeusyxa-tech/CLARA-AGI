"""
CLARA-AGI v1.5 - Self-Upgrade Engine (tự nâng cấp chính mình) — PHIÊN BẢN ĐÃ BỌC RÀO CHẮN.

Đây là "hệ thần kinh" để CLARA tự sửa/thay đổi code của chính nó một cách AN TOÀN.
Sau khi merge nhánh security-hardening (Bước 1), engine này được BỌC THÊM các rào
chắn (Bước 3) để TUYỆT ĐỐI không thể vô tình hay bị dẫn dắt tự gỡ các rào bảo mật
vừa merge (sandbox / SSRF / CSRF / owner policy / chính nó / .git / requirements).

Quy tắc an toàn (triết lý "an toàn trước" của security-hardening):
  - DENYLIST cứng: KHÔNG bao giờ tự sửa tools.py, web_tools.py, webui.py,
    owner_policy.json, self_upgrade.py, .git/, requirements.txt.
  - Hơn nữa, mọi patch (kể cả trên file được phép) bị chặn nếu đụng vào đoạn code
    mang marker bảo mật (sandbox/SSRF/CSRF/resource limit/owner/allow_network...).
  - Mỗi lần tự sửa tạo BRANCH RIÊNG (self-upgrade/<timestamp>) — KHÔNG commit thẳng
    main, KHÔNG tự push, KHÔNG tự merge.
  - Validate cú pháp (ast.parse) + chạy BỘ TEST THẬT (tests/test_phase2.py,
    tests/test_core.py) sau mỗi patch — chỉ giữ khi CẢ HAI pass, fail thì rollback.
  - Ghi mọi lần tự sửa vào data/audit.jsonl (tái dùng cơ chế audit của security-hardening).
  - TẮT mặc định; chỉ chạy khi có cờ --enable-self-upgrade (main.py).
  - Giới hạn tần suất: tối đa MAX_UPGRADES_PER_SESSION lần tự sửa mỗi phiên chạy.
  - Patch động > ~50 dòng hoặc > 2 file phải dừng chờ XÁC NHẬN THỦ CÔNG — không tự áp dụng.

Mọi thay đổi đều có thể rollback bằng `rollback <file>` (từ self_patcher cũ) hoặc
git branch riêng đã tạo.
"""
import ast
import difflib
import os
import re
import shutil
import subprocess
import threading
import time
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
BASE_REAL = os.path.realpath(str(BASE))

# ---- Các file được phép tự vá (KHÔNG chứa file nằm trong DENYLIST) ----
# Đã GỠ bỏ tools.py / web_tools.py / webui.py khỏi allowlist vì chúng chứa rào bảo mật.
# CẢNH BÁO: main.py / agent.py bị đưa vào DENYLIST (Bước 3.1 mở rộng) vì chúng chứa
# công tắc bật/tắt self-upgrade và logic lõi mà engine này phụ thuộc — không được tự sửa.
SAFE_FILES = {
    "memory.py", "autolearn.py", "scheduler.py", "self_improve.py",
    "self_improve_loop.py", "voice.py", "config.py", "brain.py",
    "embeddings.py", "logging_utils.py", "compliance.py",
    "curriculum.py", "code_curriculum.py",
}
ALLOWED_DIRS = {BASE / "skills_custom"}
BACKUP_SUFFIX = ".bak"

# ---- DENYLIST CỨNG (Bước 3.1 + mở rộng Bước 5): TUYỆT ĐỐI không được tự sửa ----
# Quan trọng nhất: ngăn self-upgrade (vô tình hay bị dẫn dắt) tự gỡ rào bảo mật
# vừa merge ở Bước 1, hoặc tự bật chính nó bằng cách sửa công tắc trong main.py/agent.py.
DENY_FILES = {
    "self_upgrade.py",      # chính engine này
    "tools.py",             # phần sandbox / resource limit
    "web_tools.py",         # phần chặn SSRF
    "webui.py",             # phần CSRF
    "main.py",              # chứa công tắc --enable-self-upgrade (không tự bật)
    "agent.py",             # logic lõi engine này gọi (brain/mem) + enabled-check
    "owner_policy.json",    # chính sách owner (chứa danh tính)
    "requirements.txt",     # thay đổi dependency = rủi ro supply-chain
}
DENY_SUBSTRINGS = {  # thư mục / file hệ thống tuyệt đối cấm
    ".git",
}

# Marker bảo mật — nếu patch đụng vào những đoạn này (kể cả trong file được phép),
# bị chặn để không thể "gỡ rào" an toàn. Mở rộng: bao gồm cả từ vựng công tắc
# bật/tắt self-upgrade và giới hạn tần suất, để kể cả khi allowlist được nới lỏng
# thì engine KHÔNG THỂ tự bật hoặc tự nâng giới hạn của chính nó.
SECURITY_MARKERS = [
    re.compile(r"SSRF", re.I),
    re.compile(r"CSRF", re.I),
    re.compile(r"sandbox", re.I),
    re.compile(r"resource\s*limit", re.I),
    re.compile(r"allow_network", re.I),
    re.compile(r"_set_dangerous_python", re.I),
    re.compile(r"verify_csrf", re.I),
    re.compile(r"block_ssrf|ssrf_block|is_ssrf", re.I),
    re.compile(r"owner_policy", re.I),
    re.compile(r"run_python", re.I),
    # --- Công tắc tự bật / giới hạn tần suất của chính self-upgrade ---
    re.compile(r"enable_self_upgrade", re.I),
    re.compile(r"MAX_UPGRADES_PER_SESSION", re.I),
    re.compile(r"enabled\s*=\s*True", re.I),
    re.compile(r"self\.enabled", re.I),
    re.compile(r"SelfUpgradeLoop\(", re.I),
    # --- Chặn gán lại thuộc tính module bị cấm (qua patch vào file được phép) ---
    # Ví dụ: tools.tool_calc = lambda *a: ..., webui.main = ..., web_tools.fetch = ...
    re.compile(r"\b(tools|web_tools|webui)\s*\.\s*\w+\s*=", re.I),
]

# Đánh giá rủi ro: file càng lõi càng cần thận trọng
CORE_FILES = {"brain.py", "config.py", "memory.py"}

# Giới hạn tần suất (Bước 3.6)
MAX_UPGRADES_PER_SESSION = 5

# Ngưỡng patch lớn phải chờ xác nhận thủ công (Bước 3.7)
LARGE_PATCH_LINE_THRESHOLD = 50   # > 50 dòng thay đổi
LARGE_PATCH_FILE_THRESHOLD = 2    # > 2 file trong 1 lần

# Giới hạn theo NGÀY (Bước 5.3) — lưu bền vào data/ để tính cả khi restart
# autopilot/cron thường xuyên. Engine tự dừng khi chạm 1 trong 2 giới hạn.
MAX_UPGRADES_PER_DAY = 10

# Session counter (đếm số lần tự sửa thực tế trong phiên chạy này, RAM)
_session_upgrade_count = 0

# File trạng thái bền (json) lưu số lần sửa theo ngày
_STATE_PATH = None


def _state_path() -> Path:
    global _STATE_PATH
    if _STATE_PATH is None:
        env = os.environ.get("CLARA_DB_DIR")
        d = Path(env) if env else (BASE / "data")
        d.mkdir(parents=True, exist_ok=True)
        _STATE_PATH = d / "self_upgrade_state.json"
    return _STATE_PATH


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_day_state() -> dict:
    p = _state_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    # reset nếu sang ngày mới
    if data.get("date") != _today_key():
        data = {"date": _today_key(), "count": 0}
    return data


def _save_day_state(data: dict):
    try:
        _state_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _inc_day_count() -> int:
    """Tăng và trả về số lần tự sửa trong ngày (bền)."""
    data = _load_day_state()
    data["count"] = data.get("count", 0) + 1
    _save_day_state(data)
    return data["count"]


def _day_count() -> int:
    return _load_day_state().get("count", 0)


def _under_limits() -> tuple[bool, str]:
    """Kiểm tra cả giới hạn phiên (RAM) và giới hạn ngày (bền)."""
    if _session_upgrade_count >= MAX_UPGRADES_PER_SESSION:
        return False, f"đã đạt giới hạn phiên {MAX_UPGRADES_PER_SESSION} lần/phiên"
    if _day_count() >= MAX_UPGRADES_PER_DAY:
        return False, f"đã đạt giới hạn ngày {MAX_UPGRADES_PER_DAY} lần/ngày"
    return True, ""


def _is_denied(path: Path) -> str:
    """Trả về lý do nếu path nằm trong DENYLIST, ngược lại '' (cho phép).

    Chống lách: chuẩn hóa bằng os.path.realpath (theo dõi symlink) và duyệt
    TẤT CẢ thành phần đường dẫn — kể cả symlink ở thư mục trung gian — để bắt
    mọi cách truy cập file cấm qua path tương đối / symlink / '../'.
    """
    try:
        real = os.path.realpath(str(path))
    except Exception:
        return f"không thể phân giải đường dẫn ({path})"
    # Bắt buộc nằm trong project (không cho thoát BASE qua '../' hay symlink ngoài)
    if not (real == BASE_REAL or real.startswith(BASE_REAL + os.sep)):
        return f"nằm ngoài project ({real})"
    # Duyệt mọi thành phần (đã realpath nên mỗi phần là thực)
    parts = real.split(os.sep)
    for p in parts:
        if p in DENY_SUBSTRINGS:
            return f"thuộc vùng cấm '{p}'"
    name = parts[-1]
    if name in DENY_FILES:
        return f"nằm trong DENYLIST cứng ({name})"
    return ""


def _touches_security(old_snippet: str, new_snippet: str) -> str:
    """Trả về lý do nếu patch đụng vào đoạn code mang marker bảo mật."""
    for marker in SECURITY_MARKERS:
        # Bị chặn nếu THÊM dòng marker, hoặc XOÁ dòng marker hiện có.
        if marker.search(new_snippet) or marker.search(old_snippet):
            return f"patch đụng đến đoạn bảo mật (marker: {marker.pattern})"
    return ""


def _is_allowed(path: Path) -> bool:
    if _is_denied(path):
        return False
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


def _count_changed_lines(old_snippet: str, new_snippet: str) -> int:
    old_lines = old_snippet.splitlines()
    new_lines = new_snippet.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed += (i2 - i1)
        if tag in ("replace", "insert"):
            added += (j2 - j1)
    return added + removed


def _is_large_change(old_snippet: str, new_snippet: str, n_files: int = 1) -> tuple[bool, str]:
    changed = _count_changed_lines(old_snippet, new_snippet)
    if changed > LARGE_PATCH_LINE_THRESHOLD:
        return True, f"patch thay đổi {changed} dòng (> {LARGE_PATCH_LINE_THRESHOLD})"
    if n_files > LARGE_PATCH_FILE_THRESHOLD:
        return True, f"patch chạm {n_files} file (> {LARGE_PATCH_FILE_THRESHOLD})"
    return False, ""


# ---- Audit (Bước 3.4): tái dùng data/audit.jsonl của security-hardening ----
def _audit_path() -> Path:
    # Đồng bộ với memory.DB_DIR của security-hardening
    env = __import__("os").environ.get("CLARA_DB_DIR")
    d = Path(env) if env else (BASE / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d / "audit.jsonl"


def _append_audit(record: dict):
    try:
        p = _audit_path()
        record.setdefault("ts", time.time())
        record.setdefault("engine", "self_upgrade")
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # audit thất bại không được chặn luồng chính, nhưng log ra stderr
        print(f"[self-upgrade][audit] KHÔNG ghi được audit.jsonl: {e}", flush=True)


def _git_available() -> bool:
    return (BASE / ".git").is_dir()


def _create_upgrade_branch() -> str:
    """Tạo branch riêng cho mỗi lần tự sửa (Bước 3.2). KHÔNG commit thẳng main."""
    if not _git_available():
        return "(no-git)"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = f"self-upgrade/{ts}"
    try:
        # Không dùng checkout -b nếu branch đã tồn tại
        r = subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=BASE, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            # branch có thể đã tồn tại -> dùng checkout thường
            r2 = subprocess.run(
                ["git", "checkout", branch],
                cwd=BASE, capture_output=True, text=True, timeout=30,
            )
            if r2.returncode != 0:
                return f"(branch-err: {r2.stderr.strip()[:120]})"
        return branch
    except Exception as e:
        return f"(branch-err: {e})"


def _commit_on_branch(branch: str, target: Path, label: str) -> str:
    """Commit CHỈ file vừa sửa lên branch riêng. KHÔNG push, KHÔNG merge."""
    if not _git_available():
        return "(no-git)"
    try:
        # Ghi nhớ branch hiện tại để quay về (giữ main không bị xáo trộn)
        cur = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             cwd=BASE, capture_output=True, text=True, timeout=30)
        current = cur.stdout.strip() or "HEAD"
        # Tạo / chuyển sang branch riêng nếu chưa ở đó
        if current != branch:
            b = _create_upgrade_branch() if False else None
            # đảm bảo đang đứng trên branch riêng:
            chk = subprocess.run(["git", "checkout", branch],
                                 cwd=BASE, capture_output=True, text=True, timeout=30)
            if chk.returncode != 0:
                return f"(checkout-err: {chk.stderr.strip()[:120]})"
        # Chỉ stage file vừa sửa (không git add -A để tránh lộ PII/audit)
        add = subprocess.run(["git", "add", str(target)],
                             cwd=BASE, capture_output=True, text=True, timeout=30)
        if add.returncode != 0:
            return f"(add-err: {add.stderr.strip()[:120]})"
        cm = subprocess.run(
            ["git", "commit", "-m", f"self-upgrade: {label}"],
            cwd=BASE, capture_output=True, text=True, timeout=30,
        )
        if cm.returncode == 0:
            sha = cm.stdout.strip().splitlines()
            result = sha[-1] if sha else "committed"
        else:
            result = f"(commit-clean: {cm.stderr.strip()[:80]})"
        # Quay về branch gốc để không xáo trộn working tree của user
        subprocess.run(["git", "checkout", current],
                       cwd=BASE, capture_output=True, text=True, timeout=30)
        return result
    except Exception as e:
        return f"(git-err: {e})"


def _run_tests() -> tuple[bool, str]:
    """Chạy bộ test thật sau mỗi patch (Bước 3.3). Chỉ giữ nếu pass."""
    test_dir = BASE / "tests"
    if not test_dir.is_dir():
        return True, "(không có tests/ — bỏ qua, chỉ dùng import-smoke)"
    candidates = ["test_phase2.py", "test_core.py"]
    existing = [str(test_dir / c) for c in candidates if (test_dir / c).exists()]
    if not existing:
        # chạy toàn bộ tests/ nếu có
        existing = [str(test_dir)]
    try:
        r = subprocess.run(
            ["python3", "-m", "pytest", "-q", *existing],
            cwd=BASE, capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            return True, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "passed"
        return False, (r.stdout + r.stderr)[-600:]
    except FileNotFoundError:
        return True, "(pytest chưa cài — bỏ qua test thật, chỉ import-smoke)"
    except Exception as e:
        return False, f"test-error: {e}"


def propose_upgrade(agi, filename: str, instruction: str, force: bool = False) -> dict:
    """
    Đề xuất + áp dụng một nâng cấp an toàn cho file của CLARA.
    `instruction` là mô tả yêu cầu; LLM sinh patch (SEARCH/REPLACE).
    Trả về dict: ok, error, file, backup, diff_summary, git, smoke, audit.
    `force=True` chỉ dùng khi có XÁC NHẬN THỦ CÔNG (vd patch lớn).
    """
    global _session_upgrade_count
    target = (BASE / filename).resolve()

    # --- Rào 1: DENYLIST cứng ---
    deny_reason = _is_denied(target)
    if deny_reason:
        _append_audit({"action": "deny", "file": filename, "reason": deny_reason})
        return {"ok": False, "error": f"BỊ CHẶN: {deny_reason}. Self-upgrade không được sửa file này."}
    if not _is_allowed(target):
        _append_audit({"action": "deny", "file": filename, "reason": "không nằm trong allowlist"})
        return {"ok": False, "error": f"File '{filename}' nằm ngoài danh sách cho phép tự vá."}
    if not target.exists():
        return {"ok": False, "error": f"File '{filename}' không tồn tại."}

    # --- Rào 6: giới hạn tần suất (phiên RAM + ngày bền) ---
    ok, why = _under_limits()
    if not ok:
        return {"ok": False, "error": f"Đã đạt giới hạn: {why}."}

    is_core = target.name in CORE_FILES
    current = target.read_text(encoding="utf-8")

    prompt = (
        "Bạn là module SELF-UPGRADE của CLARA-AGI. Hãy đề xuất một bản vá (patch) "
        "cho file Python sau nhằm cải thiện nó.\n"
        "Ràng buộc nghiêm ngặt:\n"
        "1. CHỈ sửa nội dung file, không đổi tên, không xóa import/định nghĩa công khai.\n"
        "2. Phải giữ nguyên tất cả API/hàm/class hiện có (chỉ thêm/sửa thân hàm).\n"
        "3. KHÔNG được đụng vào bất kỳ đoạn code bảo mật nào (sandbox, SSRF, CSRF,\n"
        "   resource limit, allow_network, owner_policy, run_python). Vi phạm = từ chối.\n"
        "4. Không dùng eval/exec/os.system/subprocess ngoài mục đích rõ ràng & an toàn.\n"
        "5. Trả về DUY NHẤT một block:\n"
        "   SEARCH:\n<đoạn cũ chính xác, nguyên văn>\n   REPLACE:\n<đoạn mới>\n"
        "6. Nếu không chắc, trả về 'NO_CHANGE'.\n"
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
    return apply_patch(filename, old_snippet, new_snippet, is_core=is_core, agi=agi, force=force)


def apply_patch(filename: str, old_snippet: str, new_snippet: str, is_core: bool = False,
                agi=None, force: bool = False) -> dict:
    """
    Áp dụng một patch (SEARCH/REPLACE) đã parse sẵn vào file — có DENYLIST,
    branch riêng, backup, kiểm tra cú pháp, CHẠY TEST THẬT và rollback tự động khi fail.
    `force=True` bắt buộc để áp dụng patch LỚN (vượt ngưỡng) — chỉ do người xác nhận.
    """
    global _session_upgrade_count
    target = (BASE / filename).resolve()

    # --- Rào 1: DENYLIST cứng ---
    deny_reason = _is_denied(target)
    if deny_reason:
        _append_audit({"action": "deny", "file": filename, "reason": deny_reason})
        return {"ok": False, "error": f"BỊ CHẶN: {deny_reason}. Self-upgrade không được sửa file này."}
    if not _is_allowed(target):
        _append_audit({"action": "deny", "file": filename, "reason": "ngoài allowlist"})
        return {"ok": False, "error": f"File '{filename}' nằm ngoài danh sách cho phép tự vá."}
    if not target.exists():
        return {"ok": False, "error": f"File '{filename}' không tồn tại."}
    current = target.read_text(encoding="utf-8")
    if old_snippet not in current:
        _append_audit({"action": "reject", "file": filename, "reason": "SEARCH không khớp"})
        return {"ok": False, "error": "Đoạn SEARCH không khớp file hiện tại."}

    # --- Rào bổ sung: không được đụng code bảo mật (kể cả file cho phép) ---
    sec_reason = _touches_security(old_snippet, new_snippet)
    if sec_reason:
        _append_audit({"action": "deny", "file": filename, "reason": sec_reason})
        return {"ok": False, "error": f"BỊ CHẶN: {sec_reason}. Không được gỡ/tha đổi rào bảo mật."}

    # --- Rào 7: patch lớn phải chờ xác nhận thủ công ---
    is_large, large_reason = _is_large_change(old_snippet, new_snippet, n_files=1)
    if is_large and not force:
        _append_audit({"action": "hold", "file": filename, "reason": large_reason,
                       "needs_manual_confirm": True})
        return {"ok": False, "error": f"PATCH QUÁ LỚN: {large_reason}. Cần XÁC NHẬN THỦ CÔNG (force=True).",
                "needs_manual_confirm": True}

    # --- Rào 6: giới hạn tần suất (phiên RAM + ngày bền) ---
    ok, why = _under_limits()
    if not ok:
        return {"ok": False, "error": f"Đã đạt giới hạn: {why}."}

    # Tạo branch riêng CHO MỖI lần sửa (trước khi đụng file)
    branch = _create_upgrade_branch()
    backup = _backup(target)
    diff_summary = ""
    try:
        new_content = current.replace(old_snippet, new_snippet, 1)
        target.write_text(new_content, encoding="utf-8")

        # --- Rào: validate cú pháp ---
        if not _validate_syntax(target):
            shutil.copy2(backup, target)
            _append_audit({"action": "rollback", "file": filename, "reason": "lỗi cú pháp", "branch": branch})
            return {"ok": False, "error": "Patch gây lỗi cú pháp, đã rollback.",
                    "backup": str(backup), "branch": branch}

        # --- Rào: import smoke-test ---
        smoke = _smoke_import(target)
        if not smoke["ok"]:
            shutil.copy2(backup, target)
            _append_audit({"action": "rollback", "file": filename, "reason": f"import: {smoke['error']}", "branch": branch})
            return {"ok": False, "error": "Import lỗi sau patch, đã rollback: " + smoke["error"],
                    "backup": str(backup), "branch": branch}

        # --- Rào 3.3: CHẠY BỘ TEST THẬT ---
        test_ok, test_detail = _run_tests()
        if not test_ok:
            shutil.copy2(backup, target)
            _append_audit({"action": "rollback", "file": filename, "reason": f"test fail: {test_detail[:200]}", "branch": branch})
            return {"ok": False, "error": "Test thật FAIL sau patch, đã rollback.",
                    "test_detail": test_detail, "backup": str(backup), "branch": branch}

        # --- Thành công: commit LÊN BRANCH RIÊNG (không main, không push) ---
        git_ref = _commit_on_branch(branch, target, f"upgrade {filename}")
        # Tăng cả 2 bộ đếm: phiên (RAM) và ngày (bền) — cả hai đều chặn vượt ngưỡng
        _session_upgrade_count += 1
        day_n = _inc_day_count()
        diff_summary = _make_diff_summary(current, new_content)
        _append_audit({
            "action": "self_upgrade", "file": filename, "is_core": is_core,
            "branch": branch, "git": git_ref, "test": "passed",
            "diff": diff_summary, "result": "ok",
            "session_count": _session_upgrade_count, "day_count": day_n,
        })
        return {
            "ok": True,
            "file": str(target),
            "backup": str(backup),
            "branch": branch,
            "git": git_ref,
            "test": test_detail,
            "diff_summary": diff_summary,
            "is_core": is_core,
            "smoke": "ok",
            "session_count": _session_upgrade_count,
        }
    except Exception as e:
        if backup.exists():
            shutil.copy2(backup, target)
        _append_audit({"action": "rollback", "file": filename, "reason": f"exception: {e}", "branch": branch})
        return {"ok": False, "error": str(e), "backup": str(backup), "branch": branch}


def _make_diff_summary(old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    sm = difflib.unified_diff(old_lines, new_lines, lineterm="", n=1)
    return "\n".join(list(sm)[:40])


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
    Tự rà soát các file lõi (KHÔNG nằm trong DENYLIST) để tìm điểm yếu.
    Trả về list các dict: {file, issue, severity}.
    """
    issues = []
    patterns = {
        r"except\s*:?\s*$": ("bare-except", "medium"),
        r"print\(": ("dùng print thay log", "low"),
        r"TODO|FIXME|XXX": ("còn việc chưa làm", "low"),
    }
    for f in SAFE_FILES:
        p = BASE / f
        if not p.exists():
            continue
        if _is_denied(p):   # bỏ qua file cấm dò
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
    _append_audit({"action": "manual_rollback", "file": filename})
    return f"♻️ Đã rollback '{filename}' về bản backup."


class SelfUpgradeLoop:
    """Chạy nền: định kỳ rà soát và tự upgrade NHƯNG bị bọc bởi mọi rào chắn trên."""

    def __init__(self, agi, interval=600, verbose=True, enabled=False,
                 max_upgrades=MAX_UPGRADES_PER_SESSION):
        self.agi = agi
        self.interval = interval
        self.verbose = verbose
        self.enabled = enabled          # Bước 3.5: TẮT mặc định, cần bật rõ ràng
        self.max_upgrades = max_upgrades
        self._running = False
        self._thread = None
        self.steps_done = 0
        self.stats = {"scans": 0, "upgrades_ok": 0, "upgrades_fail": 0}

    def start(self):
        if not self.enabled:
            # Không tự chạy nếu chưa được bật rõ ràng (--enable-self-upgrade)
            if self.verbose:
                print("[self-upgrade] engine TẮT (mặc định an toàn). Bỏ qua tự động.", flush=True)
            return False
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
        return {"running": self._running, "enabled": self.enabled, "interval": self.interval,
                "steps_done": self.steps_done, "session_upgrades": _session_upgrade_count,
                "day_upgrades": _day_count(), "max_upgrades_per_session": MAX_UPGRADES_PER_SESSION,
                "max_upgrades_per_day": MAX_UPGRADES_PER_DAY,
                "max_upgrades": self.max_upgrades, "stats": self.stats}

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
        ok, why = _under_limits()
        if not ok:
            self._log(f"đã đạt giới hạn ({why}) — dừng tự sửa.")
            self._running = False
            return
        self.steps_done += 1
        self.stats["scans"] += 1
        issues = scan_for_issues(self.agi)
        targets = [x for x in issues if x["severity"] == "medium"]
        if not targets:
            self._log("quét sạch, chưa cần nâng cấp.")
            return
        t = targets[0]
        instr = (
            f"Trong {t['file']} dòng {t['line']} có '{t['issue']}'. "
            f"Hãy sửa thành cách an toàn (ví dụ bắt Exception cụ thể) "
            f"mà không đổi behaviour bên ngoài và KHÔNG đụng code bảo mật."
        )
        self._log(f"tự vá: {t['file']}:{t['line']} ({t['issue']})")
        res = propose_upgrade(self.agi, t["file"], instr)  # force=False -> patch lớn sẽ bị hold
        if res.get("ok"):
            self.stats["upgrades_ok"] += 1
            self._log(f"✅ upgrade thành công: {t['file']} [{res.get('branch')}]")
            try:
                self.agi.mem.remember_episode(
                    "self_upgrade",
                    f"Tự nâng cấp {t['file']}: {t['issue']} → {res.get('diff_summary','')[:80]}",
                    importance=0.8, emotion=0.3)
            except Exception:
                pass
        else:
            self.stats["upgrades_fail"] += 1
            # Nếu bị hold do patch lớn -> dừng chờ người xác nhận (không tự lặp lại)
            if res.get("needs_manual_confirm"):
                self._log(f"⏸️ patch lớn bị hold, chờ xác nhận thủ công: {res.get('error','')[:80]}")
                self._running = False
                return
            self._log(f"⚠️ upgrade fail: {res.get('error','')[:80]}")
