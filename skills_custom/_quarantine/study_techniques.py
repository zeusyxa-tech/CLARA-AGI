"""
Study techniques coach for busy Vietnamese learners.
Teaches 5 practical fast-study methods for tech/coding.
"""
import re


def _tokenize(text: str):
    return [w for w in re.split(r"\W+", text.lower()) if w and len(w) >= 2]


def run(agi, text: str) -> str:
    text = (text or "").strip().lower()
    methods = [
        {
            "id": "spaced_repeat",
            "name": "Lặp lại phân hóa",
            "mins": ["5p", "1h sau", "1 ngày sau", "3 ngày sau", "7 ngày sau"],
            "tip": "Học 5-10 phút đầu tiên; review sau 1 giờ, 1 ngày, 3 ngày, 7 ngày.",
        },
        {
            "id": "active_recall",
            "name": "Tự kiểm tra chủ động",
            "mins": ["ngay", "trước khi ngủ"],
            "tip": "Đóng sách/laptop, tự viết/giải thích lại bằng lời hoặc giấy; kiểm tra 10 phút đầu là quan trọng.",
        },
        {
            "id": "chunking",
            "name": "Chia nhỏ + ví dụ Việt",
            "mins": ["10p/buổi"],
            "tip": "Mỗi lần học 1 khối nhỏ (ví dụ: 1 hàm Python = ý + cú pháp + ví dụ + bài tập mini).",
        },
        {
            "id": "pomodoro_focus",
            "name": "Pomodoro 25/5",
            "mins": ["25p học", "5p nghỉ"],
            "tip": "25 phút tập trung code/thực hành, 5 phút đứng dậy; sau 4 vòng nghỉ 15 phút.",
        },
        {
            "id": "teach_back",
            "name": "Dạy lại để nhớ sâu",
            "mins": ["10-20p"],
            "tip": "Giả sử dạy bạn bè/CLARA: nói to hoặc viết lại kiến thức vừa học; điểm chưa rõ chính là điểm cần ôn.",
        },
    ]

    choose = text.replace("học ", "").replace("mẹo ", "").strip()
    if not choose or choose in {"mẹo", "mẹo học"}:
        out = [
            "Mẹo học nhanh kỹ thuật/code cho người Việt ít thời gian:",
            "",
            "1. Lặp lại phân hóa",
            "2. Tự kiểm tra chủ động",
            "3. Chia nhỏ + ví dụ Việt",
            "4. Pomodoro 25/5",
            "5. Dạy lại để nhớ sâu",
            "",
            "Gõ cụ thể tên mẹo để mình giải thích chi tiết và lấy ví dụ.",
        ]
        return "\n".join(out)

    input_tokens = set(_tokenize(choose))
    candidates = []
    for m in methods:
        score = 0
        if m["id"] in choose:
            score += 10
        if m["name"].lower() in choose:
            score += 20
        tokens = set(_tokenize(m["id"] + " " + m["name"]))
        score += len(input_tokens & tokens)
        if score:
            candidates.append((score, m))
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = candidates[0][1] if candidates else None

    if not selected:
        return "Mình chưa nhớ rõ mẹo đó. Bạn thử: lặp lại phân hóa, tự kiểm tra, chia nhỏ, pomodoro, dạy lại."

    return (
        f"Mẹo: {selected['name']}\n"
        f"Thời điểm gợi ý: {', '.join(selected['mins'])}\n"
        f"Cách làm: {selected['tip']}\n"
        f"Ví dụ nhanh: Hôm nay học 'hàm Python', tối review lại, ngày mai giải thích lại cho CLARA."
    )
