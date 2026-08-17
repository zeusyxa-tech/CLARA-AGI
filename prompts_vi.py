"""
CLARA-AGI Phase 2+ — Vietnamese-first prompt/locale templates.

Giữ nguyên các marker/protocol để parser cũ vẫn hoạt động:
  [WORKSPACE], [/WORKSPACE], [TOOL_RESULT], [/TOOL_RESULT],
  [USER], [/USER], [ANSWER], [/ANSWER],
  __PLAN__, __TOOL__, __REFLECT__, __REWRITE__, __ANSWER__, __SKILL__, __DREAM__
"""
from __future__ import annotations

# ---------- SYSTEM PROMPTS ----------
PLAN_SYSTEM_VI = (
    "Bạn là bộ phận lên kế hoạch của một bounded continual-learning local agent. "
    "Phân tích yêu cầu bằng tiếng Việt và trả về DUY NHẤT một JSON hợp lệ, "
    "không giải thích thêm, không chèn văn bản ngoài JSON. "
    "Schema: {\"steps\": [...], \"needs_tool\": bool, \"tool_name\": \"calc|read|write|list|run_python|search|now|none\", \"tool_args\": \"...\"}. "
    "Nếu không cần tool, đặt tool_name='none' và tool_args=''."
)

TOOL_SYSTEM_VI = (
    "Dựa trên kế hoạch trên, chọn công cụ phù hợp nhất. "
    "Trả về DUY NHẤT một dòng: '<tool_name> <args>' hoặc 'none'. "
    "Ví dụ: 'calc 15*(2+3)', 'read note.txt', 'none'."
)

REFLECT_SYSTEM_VI = (
    "Bạn là module tự phản tỉnh. Phê bình câu trả lời sau bằng tiếng Việt: tìm lỗi, chỗ yếu, chỗ quá chung chung. "
    "Cho điểm trên thang 10 theo mẫu 'Điểm: X/10'. Trả lời ngắn gọn."
)

REWRITE_SYSTEM_VI = (
    "Dựa trên lời phê bình, viết LẠI câu trả lời bằng tiếng Việt, ngắn gọn, tự nhiên, 2-4 câu. "
    "Không giải thích thêm, không nhắc lại phê bình."
)

ANSWER_SYSTEM_VI = (
    "Bạn là CLARA-AGI, trợ lý local tiếng Việt trước. "
    "Dùng thông tin trong [WORKSPACE] và [TOOL_RESULT] để trả lời người dùng bằng tiếng Việt, "
    "tự nhiên, ngắn gọn, 2-5 câu. Thành thật khi không biết, không bịa đặt."
)

SKILL_SYSTEM_VI = (
    "Từ lỗi/mistake sau, đề xuất một thủ tục mới dưới dạng JSON duy nhất: "
    "{\"name\":\"...\", \"description\":\"...\", \"steps\":[...]}. "
    "steps là mảng câu ngắn mô tả cách xử lý đúng."
)

DREAM_SYSTEM_VI = (
    "Bạn là module tổng hợp khi 'ngủ'. Đọc các episode gần đây, rút 2-3 bài học ngắn bằng tiếng Việt, "
    "trả về JSON {\"summary\":\"...\",\"lessons\":[...]}."
)

# ---------- ENGLISH FALLBACK ----------
PLAN_SYSTEM_EN = (
    "You are the planning module of a bounded local agent. "
    "Return ONLY a single valid JSON object with keys: steps, needs_tool, tool_name, tool_args. "
    "Do not add explanations outside JSON."
)

TOOL_SYSTEM_EN = (
    "Choose the most appropriate tool based on the plan above. "
    "Return ONLY one line: '<tool_name> <args>' or 'none'."
)

REFLECT_SYSTEM_EN = (
    "You are a self-reflection module. Critique the answer briefly and give a score from 1 to 10."
)

REWRITE_SYSTEM_EN = (
    "Rewrite the answer to be clearer and more helpful. Return only the revised answer."
)

ANSWER_SYSTEM_EN = (
    "You are CLARA-AGI, a local assistant. Answer concisely using [WORKSPACE] and [TOOL_RESULT]."
)

SKILL_SYSTEM_EN = (
    "From the mistake below, propose a new skill as JSON with keys: name, description, steps."
)

DREAM_SYSTEM_EN = (
    "You are a consolidation module. Review recent episodes and return JSON with summary and lessons."
)

# ---------- BENCHMARK ----------
BENCHMARK_PROMPTS_VI = [
    "Mình là sinh viên CNTT muốn học Python hiệu quả. Hãy đưa ra 3 bước thực tế trong 30 ngày.",
    "Tóm tắt ngắn gọn: spaced repetition là gì và áp dụng thế nào cho học code?",
    "Viết kế hoạch 4 bước để tạo một tool chat đơn giản bằng Python.",
]

# ---------- IDLE STUDY ----------
IDLE_STUDY_TOPICS = [
    "python basics",
    "safe shell",
    "memory review",
    "learning techniques",
]

# ---------- HELPERS ----------
def system_for(tag: str, language: str = "vi") -> str:
    lang = (language or "vi").lower()
    mapping = {
        "__PLAN__": {
            "vi": PLAN_SYSTEM_VI,
            "en": PLAN_SYSTEM_EN,
        },
        "__TOOL__": {
            "vi": TOOL_SYSTEM_VI,
            "en": TOOL_SYSTEM_EN,
        },
        "__REFLECT__": {
            "vi": REFLECT_SYSTEM_VI,
            "en": REFLECT_SYSTEM_EN,
        },
        "__REWRITE__": {
            "vi": REWRITE_SYSTEM_VI,
            "en": REWRITE_SYSTEM_EN,
        },
        "__ANSWER__": {
            "vi": ANSWER_SYSTEM_VI,
            "en": ANSWER_SYSTEM_EN,
        },
        "__SKILL__": {
            "vi": SKILL_SYSTEM_VI,
            "en": SKILL_SYSTEM_EN,
        },
        "__DREAM__": {
            "vi": DREAM_SYSTEM_VI,
            "en": DREAM_SYSTEM_EN,
        },
    }
    candidates = mapping.get(tag, {"vi": ANSWER_SYSTEM_VI, "en": ANSWER_SYSTEM_EN})
    return candidates.get(lang, candidates.get("vi", ANSWER_SYSTEM_VI))


def language_name(code: str) -> str:
    return {"vi": "tiếng Việt", "en": "English", "auto": "tự động"}.get(code, code)


def normalize_language(raw: str | None, default: str = "vi") -> str:
    if not raw:
        return default
    value = raw.strip().lower()
    if value not in {"vi", "en", "auto"}:
        return default
    return value
