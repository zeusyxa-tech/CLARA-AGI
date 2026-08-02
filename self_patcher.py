"""
CLARA-AGI Self-Patcher.
Cho phép CLARA tự đề xuất và áp dụng patch nhỏ cho chính code của nó,
có kiểm tra an toàn, backup, smoke-test và rollback.
"""
import ast, os, re, shutil, time
from pathlib import Path

BASE = Path(__file__).parent
SAFE_FILES = {
    "tools.py", "memory.py", "web_tools.py", "autolearn.py",
    "scheduler.py", "self_improve.py", "voice.py", "webui.py",
}
ALLOWED_DIRS = {BASE / "skills_custom"}
BACKUP_SUFFIX = ".bak"


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


def propose_patch(agi, filename: str, instruction: str) -> dict:
    """
    Dùng LLM để đề xuất patch cho file cụ thể.
    Trả về dict với khóa: ok, error, patch, backup_path, diff_summary, file
    """
    target = (BASE / filename).resolve()
    if not _is_allowed(target):
        return {"ok": False, "error": f"File '{filename}' không nằm trong danh sách cho phép."}
    if not target.exists():
        return {"ok": False, "error": f"File '{filename}' không tồn tại."}

    current = target.read_text(encoding="utf-8")
    prompt = (
        "Bạn là module self-patch của CLARA-AGI. Hãy đề xuất patch cho file Python sau.\n"
        "Ràng buộc:\n"
        "1. CHỈ sửa nội dung file, không đổi tên file, không xóa module.\n"
        "2. Trả về DUY NHẤT một block patch định dạng:\n"
        "   SEARCH:\n"
        "   <đoạn cũ chính xác>\n"
        "   REPLACE:\n"
        "   <đoạn mới>\n"
        "3. Nếu không chắc, trả về 'NO_CHANGE'.\n"
        f"Tên file: {filename}\n"
        f"Yêu cầu thay đổi: {instruction}\n"
        "=== FILE CONTENT ===\n"
        f"{current[:12000]}\n"
        "=== END FILE ==="
    )
    raw = agi.brain.think("__ANSWER__", prompt, temperature=0.2, num_predict=1200)
    if "NO_CHANGE" in raw:
        return {"ok": False, "error": "Model đề xuất không thay đổi.", "raw": raw}

    m = re.search(r"SEARCH:\s*(.*?)\s*REPLACE:\s*(.*)", raw, re.S)
    if not m:
        return {"ok": False, "error": "Không parse được patch.", "raw": raw}

    old_snippet = m.group(1).strip()
    new_snippet = m.group(2).strip()
    if old_snippet not in current:
        return {"ok": False, "error": "Đoạn SEARCH không khớp file hiện tại.", "raw": raw}

    backup = _backup(target)
    try:
        new_content = current.replace(old_snippet, new_snippet, 1)
        target.write_text(new_content, encoding="utf-8")
        if not _validate_syntax(target):
            shutil.copy2(backup, target)
            return {"ok": False, "error": "Patch gây lỗi cú pháp, đã rollback.", "backup": str(backup)}
        return {
            "ok": True,
            "file": str(target),
            "backup": str(backup),
            "diff_summary": f"Đã thay {len(old_snippet)} bytes → {len(new_snippet)} bytes",
            "patch": raw,
        }
    except Exception as e:
        if backup.exists():
            shutil.copy2(backup, target)
        return {"ok": False, "error": str(e), "backup": str(backup)}


def smoke_test(agi, filename: str) -> dict:
    target = BASE / filename
    if not target.exists():
        return {"ok": False, "error": "File không tồn tại."}
    if not _validate_syntax(target):
        return {"ok": False, "error": "Lỗi cú pháp."}
    # thử import module đổi tên tạm để tránh side-effect
    mod_name = f"__clara_smoke_{target.stem}__"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(mod_name, str(target))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {"ok": True, "module": mod_name, "exports": [a for a in dir(mod) if not a.startswith("_")][:20]}
    except Exception as e:
        return {"ok": False, "error": f"Import lỗi: {e}"}


def list_backups():
    return [p.name for p in BASE.glob(f"*{BACKUP_SUFFIX}") if p.is_file()]


def rollback(filename: str) -> str:
    target = BASE / filename
    bkp = target.with_suffix(target.suffix + BACKUP_SUFFIX)
    if not bkp.exists():
        return f"❌ Không có backup cho '{filename}'."
    shutil.copy2(bkp, target)
    return f"♻️ Đã rollback '{filename}' về bản backup."
