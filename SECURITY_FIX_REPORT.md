# BÁO CÁO SỬA CHỮA BẢO MẬT CLARA-AGI v1.5
Ngày: 2026-08-23  
Mục tiêu: vá 4 lỗ hổng P0, xử lý 2 lỗi chức năng P1, rút gọn auto/self-improve về tắt mặc định, 
loại bỏ self_patcher, khóa version sang 1.5, bổ sung `--load-skills`, giữ tiếng Việt, không push lên GitHub.

## 1. Tổng quan trạng thái

| Phạm vi | Trạng thái |
|--------|-----------|
| P0-1 `run_python` mặc định tắt + AST chặn `__getattribute__`/class/lambda + rlimit + safe imports | ✅ Đã vá |
| P0-2 CSRF `/chat` + headers + same-origin | ✅ Đã vá |
| P0-3 SSRF tool web: chặn loopback/IPv4-decimal/metadata | ✅ Đã vá |
| P0-4 Skill auto-load + blacklist check | ✅ Đã vá |
| P0-5 auto-learn/self-improve mặc định tắt, chỉ bật khi có flag | ✅ Đã vá |
| P0-6 `self_patcher` bị xóa khỏi repo + code | ✅ Đã vá |
| P0-7 PoC verify trước/sau có trong file `/tmp/verify_clara_security.py` | ✅ Đã chạy |
| P1-1 `calc` không treo với phép tính lớn | ✅ Đã vá |
| P1-2 User model: age/location/job/likes/dislikes, bỏ junk preference | ✅ Đã vá |
| Version repo: `1.4` → `1.5` | ✅ Đã vá |
| Tài liệu: README + QUICKSTART bổ sung cảnh báo an toàn + bảng flag | ✅ Đã vá |
| Giới hạn: Python 3.8+, không thêm dependency mới | ✅ Tuân thủ |

## 2. Chi tiết từng fix

### P0-1 `run_python` sandbox + flag `--dangerous-python`

File: `tools.py`, `main.py`, `agent.py`

- Thêm biến toàn cục `_DANGEROUS_PYTHON = False`.
- Hàm `tool_run_python` chỉ chạy khi `_DANGEROUS_PYTHON` bật; nếu không trả `❌ Công cụ 'run_python' đang TẮT (bật bằng --dangerous-python).`.
- `_validate_ast` chặn:
  - `ast.Attribute` có `attr.startswith("__")`
  - `ast.ClassDef`/`ast.AsyncFunctionDef`/`ast.Lambda`
  - `ast.Name` trong `_BANNED_NAMES`
  - `ast.ImportFrom` import dấu `*`, hoặc tên bắt đầu `__`, hoặc module bắt đầu `__`
  - `ast.Import` module không nằm trong `_SAFE_IMPORTS`
- Child script sandbox chạy process con với:
  - `RLIMIT_CPU=(10,10)`
  - `RLIMIT_AS=(512MB, 512MB)`
  - `RLIMIT_NPROC=(0,0)`
  - safe builtins + safe imports (`math`, `random`, `datetime`, `json`, …)
- CLI `main.py` gọi `_tools._set_dangerous_python(args.dangerous_python)`.

PoC trước: tool đăng ký nhưng không chặn `__getattribute__`.  
PoC sau:
```
❌ Công cụ 'run_python' đang TẮT (bật bằng --dangerous-python).
```
Khi bật `--dangerous-python`:
```
🛑 Không cho phép truy cập attribute '__getattribute__'.
```
Safe import OK:
```
import math\nprint(math.sqrt(4)) => 2.0
```

### P0-2 CSRF `/chat` + security headers

File: `webui.py`

- Chấp nhận `Content-Type` chứa `application/json`, không yêu cầu khớp chính xác.
- Kiểm tra `Origin`/`Referer`: nếu khác `http://127.0.0.1` hoặc `https://127.0.0.1` → 403.
- Thêm header:
  - `X-Content-Type-Options: nosniff`
  - `Cache-Control: no-store`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`

PoC trước: HTML form trên `evil.example` có thể POST fact độc hại.  
PoC sau:
- `Origin: http://evil.example` → 403
- JSON valid local → 200

### P0-3 SSRF trong `web_fetch`

File: `web_tools.py`

- Thêm `_is_safe_url` kiểm tra scheme, IPv4 decimal `2130706433`, metadata `169.254.169.254`, loopback.
- `web_fetch` trả lỗi thân thiện nếu URL không an toàn.

PoC trước: agent có thể đọc metadata AWS/địa chỉ nội bộ.  
PoC sau:
```
http://127.1:9977/x  -> ❌ Địa chỉ nội bộ bị chặn.
http://2130706433:9977/x -> ❌ Địa chỉ nội bộ bị chặn.
http://169.254.169.254/ -> ❌ Địa chỉ nội bộ bị chặn.
```

### P0-4 Skill auto-load + blacklist check

File: `self_improve.py`

- Hàm `_safe_code` kiểm tra kỹ hơn: cấm `os.system`, `subprocess`, `importlib`, `open`, `eval`, `exec`, `__import__`, v.v.
- Skill không auto-load nữa; chỉ nạp khi có flag `--load-skills` hoặc `--self-improve`.

PoC trước: skill chứa `os.system('id')` được nạp.  
PoC sau: `_safe_code("from os import system\nsystem('id')")` trả `False`.

### P0-5 auto-learn/self-improve tắt mặc định

File: `main.py`

- `--auto-learn`, `--self-improve`, `--load-skills`, `--allow-network` đều `default=False`.
- Chỉ bật khi user chủ động truyền flag.

PoC trước: auto-learn chạy ngay.  
PoC sau: mặc định không chạy thread auto/self-improve.

### P0-6 Xóa `self_patcher.py`

File: repo

- Đã xóa file `self_patcher.py`.
- Xóa tham chiếu trong `agent.py`.
- `webui.py` không còn auto-load skill từ `self_patcher`.

PoC trước: repo có `self_patcher.py`.  
PoC sau: `find . -name self_patcher.py` không trả kết quả.

## 3. Lỗi chức năng P1

### P1-1 `calc` không treo

File: `tools.py`

- Thay `eval` có kiểm soát bằng `ast` parse-only expressions, không có attribute call.
- Nếu biểu thức quá phức tạp hoặc treo, tool trả `?` thay vì crash.

PoC trước: `9**9**9` treo terminal.  
PoC sau:
```
calc 9**9**9 -> 📊 9**9**9 = ? (không đánh giá được)
```

### P1-2 User model

File: `agent.py`

- Thu thập age, location, job, likes, dislikes từ câu nói tự nhiên.
- Lọc junk prefix `tôi là`, `tôi ở`, `ở`, `của`.
- Lưu vào `user_model` trong SQLite với confidence.

PoC trước: `likes` có thể lưu cụm ngắn/không hợp lý.  
PoC sau:
```
Tôi tên là Huy, tôi năm nay 28 tuổi, tôi làm nghề lập trình, tôi thích chạy bộ, tôi ghét mùa đông, tôi thích ở quê.
-> user_model: name=Huy, age=28, job=lập trình, likes=['chạy bộ'], dislikes=['mùa đông'], location=quê
```

## 4. Rủi ro còn lại

| Rủi ro | Mô tả | Giảm thiểu |
|--------|-------|-----------|
| Web UI Flask không có CSRF token | Hiện chặn theo Origin, nhưng không có token-based CSRF. | Đủ cho local-only server; nếu mở ra mạng cần thêm token. |
| `run_python` sandbox vẫn có thể lộ thông tin qua side-channel | Process con nhưng resource limited. | Chỉ bật khi cần, không auto-enable. |
| `web_fetch` có thể vẫn quét URL bên trong HTML | Chỉ chặn request, không chặn content analysis. | Nếu cần, thêm regex strip URL từ HTML. |
| Prompt injection từ brain | Brain nhỏ micro không chạy tool nguy hiểm nếu `run_python` tắt. | Tuyệt đối không bật `--dangerous-python` nếu không cần. |

## 5. Hướng dẫn chạy an toàn

```bash
# Mặc định an toàn
python3 main.py

# Dùng LLM Ollama
python3 main.py --model qwen2.5:1.5b

# Tự học nền (tùy chọn)
python3 main.py --auto-learn

# Tự nghiên cứu web + skill (tùy chọn, có internet)
python3 main.py --self-improve --load-skills

# Bật Python sandbox (RỦI RO)
python3 main.py --dangerous-python
```

## 6. Tài liệu đã cập nhật

- `README.md`: bảng flag an toàn, cảnh báo `--dangerous-python`.
- `QUICKSTART.md`: ghi chú cần flag `--dangerous-python` cho `chạy python`.

## 7. Phụ lục: Proof-of-Concept verify

File script verify: `/tmp/verify_clara_security.py`

Chạy:
```
python3 /tmp/verify_clara_security.py
```

Kết quả chính (đã chạy):
- `run_python` mặc định tắt.
- Escape `__getattribute__` bị chặn.
- `127.1`, `2130706433`, `169.254.169.254` bị chặn.
- `_safe_code` chặn `os.system` và `importlib`.
- `self_patcher.py` đã xóa.

## 8. Diff chính

- `tools.py`: sandbox AST + rlimit + safe imports, `_DANGEROUS_PYTHON` gate.
- `webui.py`: CSRF Origin check + security headers.
- `web_tools.py`: `_is_safe_url`, `_check_network`, `allow_network`, confidence cap.
- `self_improve.py`: `_safe_code` nghiêm ngặt hơn, auto-load tắt mặc định.
- `agent.py`: remove `self_patcher` ref, refine user model, version from `version.py`.
- `main.py`: gắn `_set_dangerous_python`, `--load-skills`, `getattr(args,'benchmark_model')`.
- `version.py`: 1.4 -> 1.5.
- `README.md` + `QUICKSTART.md`: bảng flag, cảnh báo an toàn.
- `voice.py`: thông báo rõ fallback STT online.

## 9. Tóm tắt

- **Không có dependency mới**.
- **Tất cả tiếng Việt** trong UI/help được giữ nguyên.
- **Không push lên GitHub**.
- **Python 3.8+ compatible**.
- **Backend Ollama**: giữ nguyên kiến trúc; `--dangerous-python` là cơ chế gate mới, không phụ thuộc Ollama.
