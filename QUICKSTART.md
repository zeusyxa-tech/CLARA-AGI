# 🚀 HƯỚNG DẪN CHẠY NHANH (dành cho người mới)

## ⏱️ Tóm tắt trong 5 phút

### 1. Chạy ngay không cần cài gì cả (chế độ nhẹ nhất)
- **Windows**: Nhấp đúp `run.bat`
- **Linux/macOS**: Mở Terminal, gõ `chmod +x run.sh && ./run.sh`
- Hoặc cách phổ biến nhất: mở terminal trong thư mục này và gõ:
  ```
  python main.py
  ```

👉 Lần đầu CLARA sẽ dùng **micro brain** (template), đủ trải nghiệm toàn bộ kiến trúc.

### 2. Nâng cấp trí tuệ với AI thực thụ (LLM local)

**Cách dễ nhất:**
- **Windows**: nhấp đúp `install_ollama.bat`
- **Linux/macOS**: mở terminal gõ `bash install_ollama.sh`

Script này sẽ tự cài **Ollama** (phần mềm chạy AI trên máy bạn) và tải model `qwen2.5:1.5b` (~900MB, chạy được trên máy 6-8GB RAM).

**Cách tay (nếu script bị lỗi):**
1. Tải Ollama ở **https://ollama.com/download** rồi cài như phần mềm bình thường
2. Mở Terminal / CMD gõ: `ollama pull qwen2.5:1.5b`
3. Chạy lại `run.bat` / `./run.sh` — CLARA tự nhận Ollama

> 💡 Máy rất yếu (4GB RAM) dùng model nhẹ hơn: `ollama pull qwen2.5:0.5b` (~350MB)
> 💡 Máy khỏe (8GB+ RAM) dùng: `ollama pull qwen2.5:3b` (~1.9GB)

### 3. Giao diện web (đẹp, giống ChatGPT)
```
pip install flask
python main.py --web
```
Tự động mở trình duyệt tại http://127.0.0.1:5000

### 4. Giao diện giọng nói (nói vào, nghe ra)
```
pip install SpeechRecognition pyttsx3 pyaudio
python main.py --voice
```

---

## 📝 Điều gì xảy ra sau khi chạy?

- CLARA sẽ chào bạn và bắt đầu nhớ bạn
- Bảo nó: `tôi tên là ..., tôi ở ..., tôi thích ...` — nó sẽ nhớ
- Hỏi lại: `tôi tên gì?` — nó trả lời đúng
- Bảo nó: `tính (2^8 * pi) / 17` — nó dùng công cụ tính
- Bảo nó: `chạy python: print(sum(range(1,101)))` — nó chạy code Python sandbox an toàn
- Sau mỗi câu trả lời bạn có thể nói `tốt` hoặc `tệ vì ...` để nó học
- Gõ `commands` để xem toàn bộ lệnh
- Gõ `status` để xem bộ não của nó đang hoạt động ra sao
- Gõ `quit` để thoát — **mọi thứ nó học được giữ lại cho lần sau**

---

## ❓ Câu hỏi thường gặp

**Q: Python tôi cần phiên bản nào?**
A: Python 3.8 trở lên. Kiểm tra: `python --version`. Nếu chưa có, tải ở https://python.org (Windows nhớ tích "Add Python to PATH" khi cài).

**Q: Tôi có thể chạy không cần internet không?**
A: Có — sau khi cài xong Ollama và pull model, bạn có thể ngắt mạng hoàn toàn, CLARA vẫn chạy bình thường.

**Q: File nó ghi ở đâu?**
A: Mọi thứ CLARA biết (trí nhớ, tính cách, thủ tục tự tạo) nằm trong thư mục `data/clara.db`. Xóa thư mục `data` là nó "sinh ra lại từ đầu". File nó đọc/ghi khi nói chuyện nằm trong `workspace/`.

**Q: Làm sao để sao lưu trí nhớ của CLARA?**
A: Sao lưu thư mục `data/` là đủ. Gõ `export` trong lúc nói chuyện cũng sẽ xuất ra file JSON trong `data/`.

**Q: Lỡ nó chạy code Python phá máy tôi thì sao?**
A: Không sao — code chạy trong sandbox (chặn `open`, `eval`, `exec`, import bừa, timeout 8s, chạy process con bị cô lập) và chỉ có thể ghi file trong thư mục `workspace/`. Nó không thể hỏng hệ thống của bạn.

**Q: Chạy chậm/không nhận Ollama?**
A: Chạy `python main.py --micro` để về chế độ micro brain, hoặc kiểm tra Ollama đã chạy chưa bằng cách mở trình duyệt vào http://localhost:11434 — nếu thấy "Ollama is running" là OK.

---

## 📂 Cấu trúc thư mục

```
CLARA_AGI/
├── run.bat / run.sh        ← ⭐ NHẤP ĐÚP ĐỂ CHẠY
├── install_ollama.bat/sh   ← ⭐ NHẤP ĐÚP ĐỂ CÀI AI THẬT
├── main.py                 ← Khởi chạy
├── agent.py                ← Bộ não (vòng lặp 9 bước)
├── brain.py                ← Kết nối LLM / Micro fallback
├── memory.py               ← Bộ nhớ 3 lớp
├── tools.py                ← Công cụ (tính/file/python/search)
├── webui.py                ← Giao diện web
├── voice.py                ← Giao diện giọng nói
├── data/                   ← (tự tạo) trí nhớ DB
└── workspace/              ← File CLARA được phép đọc/ghi
```

Chúc bạn vui với "đứa con AI" của mình! 🧬

---

## 💤 Chế độ TỰ HỌC KHI TREO MÁY (mới ở v1.1)

Từ phiên bản v1.1, bạn có thể bảo CLARA **tự học ngay cả khi bạn không nói chuyện với nó**:
- Tự phản tỉnh về các câu trả lời cũ bị điểm kém
- Tự đặt câu hỏi và tự trả lời dựa trên kiến thức đang có
- Củng cố kiến thức (phát hiện mâu thuẫn, nén fact trùng)
- Tự hoàn thành mục tiêu và đề xuất mục tiêu mới
- "Ngủ mơ" tổng hợp bài học
- Tò mò chuẩn bị câu hỏi để hỏi bạn khi bạn quay lại

### Cách bật
**Cách 1 (dễ):** nhấp đúp `run_idle.bat` (Windows) hoặc chạy `./run_idle.sh` (Linux/macOS)

**Cách 2 (dùng lệnh):**
```
python3 main.py --auto-learn
```

Tùy chỉnh:
```
python3 main.py --auto-learn --idle-interval 60     # tự học mỗi 60 giây (nhẹ CPU hơn)
python3 main.py --auto-learn --model qwen2.5:0.5b   # dùng model nhẹ cho máy rất yếu
```

### Lệnh trong lúc đang chat
- `autolearn on` — bật tự học
- `autolearn off` — tắt tự học
- `autolearn status` — xem đã tự học được bao nhiêu bước

> 💡 Mẹo: nếu bạn để máy cả đêm treo CLARA với `--auto-learn`, sáng hôm sau mở lên
> bạn sẽ thấy nó đã tự học được rất nhiều thứ và thậm chí có câu hỏi tò mò cho bạn.
> Không tốn nhiều pin/CPU vì mỗi bước tự học rất nhẹ, cách nhau 25 giây mặc định.

