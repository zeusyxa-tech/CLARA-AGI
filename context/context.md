# CLARA-AGI — Context for AI-assisted upgrade

## 1. Mục tiêu
- Đây là repo CLARA-AGI phiên bản đang harden security + cải thiện runtime an toàn.
- Mục tiêu vận hành: **giúp người, giúp robot/AI khác, phục vụ nhân loại, bảo vệ môi trường**.
- Chiến lược tiến hóa: giữ nguyên behavior cũ khi không có lý do thay đổi, thêm chế độ an toàn mặc định, nâng cấp từng phần có kiểm chứng.

## 2. Trạng thái repo hiện tại
- Branch: `security-hardening`
- Commit gần nhất: `494ff2a fix(security): hardening P0+P1 (sandbox, ssrf, csrf, skills, defaults, audit, calc, p1)`
- Không có secret/API key trong repo. Các file runtime như `data/clara.db` không được commit.
- Môi trường chạy hiện tại: `/home/gpd/CLARA-AGI/.venv`, venv tạm `/tmp/clara_v` có thể dùng cho test/verify.

## 3. Verify vừa chạy — kết quả
### B1: calc DoS
- Lệnh: `time tool_calc('9**9**9')`
- Kết quả: treo và timeout ở mức kiểm soát, không rơi vào DoS vô hạn.
- Ý nghĩa: đã có rào chặn tuyến tính về thời gian ở runtime test.

### B2: sandbox
- `run_python`/`python` không có trong `TOOLS` mặc định.
- Kích hoạt cần cờ `--dangerous-python`.
- PoC escape trả về: tool đang TẮT.
- Kết luận: sandbox đã tắt default, escape vector bị chặn ở lớp kích hoạt.

### B3: SSRF
- 3 vector đều bị chặn do mạng tắt mặc định.
- Thông báo: `Mạng đã tắt: bật --allow-network để sử dụng web research.`
- Không có dữ liệu nội bộ/IMDS lọt ra.

### B4: skills
- `def _fn(agent, arg)` tồn tại và đang được dùng để gắn skill an toàn.
- Thư mục `skills_custom/active/` rỗng.
- Không nạp skill mặc định; chỉ nạp khi người dùng/diễn viên có ý định rõ ràng.
- Quarantine đã tồn tại dưới `skills_custom/_quarantine`.

### B5: CSRF runtime
- CSRF với `Content-Type: text/plain` + `Origin: evil.example` → `415`.
- JSON chuẩn → `200`, nội dung có `22`.
- `user_model` không ghi `name` từ request giả.
- Web server dừng sạch.

## 4. Kiến trúc an toàn hiện tại
- **Defaults**: `--dangerous-python` tắt, mạng tắt, không self-improve, không auto-learn.
- **Sandbox**: bật bằng cờ rõ ràng; chạy process riêng, có timeout, AST validation, giới hạn resource.
- **SSRF**: kiểm tra scheme, DNS -> IP, chặn loopback/private/link-local/reserved/multicast IPv4/IPv6.
- **CSRF**: middleware kiểm tra origin/content-type/accept, chặn cross-origin plain.
- **Skills**: chỉ register khi người dùng/diễn viên chủ động bật; mặc định về 0.
- **Audit**: có `data/audit.jsonl` cho sự kiện bảo mật quan trọng.

## 5. Hướng nâng cấp tiếp theo
### 5.1 Ổn định trước khi mở rộng
- Giữ default an toàn; chỉ mở tool khi người dùng đọc hiểu rủi ro.
- Thêm test regression cho calc/sandbox/ssrf/csrf/skills.
- Đặt mục tiêu kiểm chứng bằng test, không bằng “chạy xem thế nào”.

### 5.2 Dạy/nâng cấp qua context
- Dùng file `context/context.md` này làm bộ nhớ chung giữa người và AI.
- AI có thể đề xuất patch nhỏ theo đúng chính sách; người xác nhận trước khi apply.
- Ưu tiên patch có giới hạn: đổi 1 file, giữ behavior, có test mô tả.

### 5.3 Danh sách lộ trình đề xuất
1. Fix calc DoS nghiêm ngặt hơn bằng giới hạn kích thước biểu thức.
2. Thêm test chính thức trong `tests/` cho 4 vector trên.
3. Tạo CLI `clara security verify` chạy 5 bước tự động.
4. Bổ sung policy CLI để xem/export security state hiện tại.
5. Rà tool mới khi cần mở: quy trình đánh giá rủi ro trước khi đổi default.

## 6. Cách đọc file này cho AI
- Đọc toàn bộ phần này trước khi đề xuất thay đổi.
- Chỉ đề xuất thay đổi nhỏ, có thể kiểm chứng, phù hợp với mục tiêu an toàn và pháp luật Việt Nam.
- Mọi thay đổi cần có lý do rõ, trạng thái trước/sau, và cách kiểm tra.

## 7. Cách đọc file này cho người dùng
- Dùng để reset ngữ cảnh sau mỗi phiên hoặc khi đổi agent.
- Có thể bổ sung quy tắc riêng ở phần cuối file.
- Khi muốn tiến xa hơn, yêu cầu AI tạo thêm `context/roadmap.md` theo chủ đề cụ thể.
