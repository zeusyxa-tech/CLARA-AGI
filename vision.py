"""
CLARA-AGI v1.3 - Vision module.
Hỗ trợ:
- OpenAI-compatible vision API qua OPENAI_API_BASE/OPENAI_API_KEY
- Phân tích cơ bản local bằng Pillow nếu không có API
"""
import base64
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


def _read_image(path: str):
    p = Path(path)
    if not p.exists():
        return None, f"Không tìm thấy ảnh: {p}"
    if not _HAS_PIL:
        return None, "Thiếu Pillow để đọc ảnh. Cài: pip install Pillow"
    try:
        img = Image.open(p)
        info = {
            "path": str(p),
            "format": getattr(img, "format", None),
            "mode": getattr(img, "mode", None),
            "size": getattr(img, "size", (0, 0)),
            "width": getattr(img, "width", 0),
            "height": getattr(img, "height", 0),
        }
        try:
            small = img.resize((64, 64))
            pixels = list(small.getdata())
            if info["mode"] == "RGBA":
                pixels = [(r, g, b) for r, g, b, _ in pixels]
            elif info["mode"] == "L":
                pixels = [(v, v, v) for v in pixels]
            r_avg = sum(p[0] for p in pixels) / len(pixels)
            g_avg = sum(p[1] for p in pixels) / len(pixels)
            b_avg = sum(p[2] for p in pixels) / len(pixels)
            brightness = (r_avg + g_avg + b_avg) / (255 * 3)
            info["brightness"] = round(brightness, 3)
            info["avg_color"] = (round(r_avg), round(g_avg), round(b_avg))
        except Exception:
            pass
        return info, None
    except Exception as e:
        return None, f"Lỗi đọc ảnh: {e}"


def _encode_image(path: str, max_bytes: int = 4 * 1024 * 1024) -> str:
    p = Path(path)
    if p.stat().st_size > max_bytes:
        raise ValueError(f"Ảnh quá lớn ({p.stat().st_size} bytes), tối đa {max_bytes} bytes")
    with open(p, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("utf-8")


def analyze_image_openai_compatible(image_path: str, prompt: str = "Mô tả ngắn gọn nội dung ảnh này bằng tiếng Việt.") -> str:
    base_url = os.environ.get("OPENAI_API_BASE", "").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    if not base_url:
        return "Chưa cấu hình OPENAI_API_BASE cho vision."
    b64 = _encode_image(image_path)
    url = f"{base_url}/chat/completions"
    payload = {
        "model": os.environ.get("CLARA_VISION_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300,
    }
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    with urlopen(req, timeout=120) as resp:
        j = json.loads(resp.read())
    choice = (((j.get("choices") or [{}])[0]).get("message") or {})
    return (choice.get("content") or "").strip()


def analyze_image_basic(image_path: str, prompt: str = "") -> str:
    info, err = _read_image(image_path)
    if err:
        return err
    lines = [
        f"Ảnh: {info['path']}",
        f"Kích thước: {info['width']}x{info['height']} {info.get('format','')}",
    ]
    if "brightness" in info:
        label = "tối" if info["brightness"] < 0.3 else "sáng" if info["brightness"] > 0.7 else "bình thường"
        lines.append(f"Độ sáng: {info['brightness']} ({label})")
    if "avg_color" in info:
        r, g, b = info["avg_color"]
        lines.append(f"Màu trung bình: RGB({r},{g},{b})")
    if prompt:
        lines.append(f"Yêu cầu: {prompt}")
    lines.append("Gợi ý: để phân tích nội dung thật, cấu hình vision API.")
    return "\n".join(lines)


def analyze_image(image_path: str, prompt: str = "") -> str:
    p = Path(image_path)
    if not p.exists():
        return f"Không tìm thấy ảnh: {image_path}"
    if not prompt:
        prompt = "Mô tả ngắn gọn nội dung ảnh này bằng tiếng Việt."
    try:
        return analyze_image_openai_compatible(image_path, prompt)
    except Exception as e1:
        try:
            return analyze_image_basic(image_path, prompt)
        except Exception as e2:
            return f"❌ Lỗi vision: API={e1}; local={e2}"


def tool_vision(agent, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "Dùng: vision <đường_dẫn_ảnh> | <câu hỏi>"
    parts = text.split("|", 1)
    image_path = parts[0].strip()
    prompt = parts[1].strip() if len(parts) > 1 else ""
    if not image_path:
        return "Thiếu đường dẫn ảnh."
    return analyze_image(image_path, prompt)
