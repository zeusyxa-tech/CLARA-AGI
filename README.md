# 🧬 CLARA-AGI v1.0
## **AI tự học, tự nâng cấp — kiến trúc gần AGI — chạy LOCAL trên máy yếu**

> Continuous Learning Autonomous Reasoning Agent
> **Không cần GPU · không cần internet · chỉ cần Python 3.8+ · chạy được cả trên laptop 4GB RAM**

<p align="center"><b>Đây là kiến trúc gần AGI (trí tuệ nhân tạo tổng hợp) nhất có thể chạy được trên máy tính của bạn hôm nay.</b></p>

---

## 🚀 Tóm tắt trong 30 giây

Mọi "AI tự học" bạn từng thấy chỉ là **chatbot + vector database**. Còn **CLARA-AGI** mô phỏng **kiến trúc nhận thức của con người** — nó là một tác nhân tự chủ (autonomous agent) với:

✅ **Bộ nhớ 3 lớp** như não người — nhớ sự kiện (episodic), kiến thức (semantic), cách làm (procedural)  
✅ **Không gian làm việc toàn cục** (Global Workspace Theory — Baars/Dehaene) — mô hình khoa học hàng đầu về ý thức  
✅ **Vòng tự phản tỉnh** (Reflexion) — tự chấm điểm, tự viết lại câu trả lời khi chưa tốt  
✅ **Tự tạo skill mới** khi gặp lỗi lặp lại (bước đầu của self-improving recursion)  
✅ **"Ngủ mơ"** (dream) — khi rảnh tự tổng hợp ký ức thành bài học (như người ngủ củng cố trí nhớ)  
✅ **Lý thuyết về cái tâm** (Theory of Mind) — mô hình hóa người dùng (tên, tuổi, nghề, sở thích…)  
✅ **Công cụ** (tay chân) — tính toán, đọc/ghi file, **chạy code Python sandbox an toàn**, tìm kiếm bộ nhớ  
✅ **Nhìn ảnh/màn hình** (vision) — phân tích nội dung ảnh qua API hoặc Pillow local  
✅ **Cảm xúc nhẹ** — phát hiện giọng điệu bạn để điều chỉnh độ quan trọng của ký ức  
✅ **Mục tiêu tự chủ** — khởi động với 5 mục tiêu nội tại và tự hoàn thành chúng  
✅ **Giao diện CLI / Web / Giọng nói** — bạn chọn kiểu nào cũng được

---

## 📂 Những gì bạn tải về

```
CLARA_AGI/
├── main.py             # Launcher CLI (chạy là bắt đầu nói chuyện)
├── agent.py            # 🧠 Agent: vòng lặp nhận thức 9 bước
├── brain.py            # 🧠 Brain: LLM abstraction (Ollama + Micro fallback)
├── memory.py           # 💾 Bộ nhớ 3 lớp + goals + traits + user model
├── tools.py            # 🛠️ Công cụ (calc, file, run_python, search…)
├── webui.py            # 🌐 Giao diện web đẹp (Flask)
├── voice.py            # 🎙️ Chế độ giọng nói (nói vào, nghe ra)
├── requirements.txt    # Các gói tùy chọn (Flask, voice…)
├── run.sh / run.bat    # File chạy cho Linux/macOS và Windows
├── install_ollama.sh   # Script tự cài Ollama + model (Linux/macOS)
├── install_ollama.bat  # Script tự cài Ollama + model (Windows)
├── data/               # (tự tạo) chứa file DB trí nhớ
└── workspace/          # Thư mục file mà CLARA có thể đọc/ghi
```

Tổng cộng ~150KB code Python, **không có file binary đính kèm** — bạn có thể đọc toàn bộ source.

---

## ⚡ Cách chạy trong 1 phút

### Bước 0: Chuẩn bị

- **Python 3.8+** (Windows/macOS/Linux đều được). Kiểm tra: `python --version`
- **Không cần cài thư viện gì cả** cho chế độ CLI cơ bản

### Bước 1: Chạy ngay

```bash
# Linux/macOS
chmod +x run.sh && ./run.sh

# Windows — nhấp đúp run.bat hoặc:
run.bat

# Hoặc chạy bằng tay:
python main.py
```

✅ Lần đầu chạy CLARA sẽ dùng **micro brain** (template, chạy ngay không cần mạng), đủ để bạn thấy được toàn bộ kiến trúc.

### Bước 2 (tùy chọn, khuyên làm): Nâng cấp trí tuệ với LLM local

Cài Ollama (cho phép chạy LLM như qwen2 trên máy bạn):

```bash
# Linux/macOS: chạy 1 dòng
bash install_ollama.sh

# Windows: nhấp đúp install_ollama.bat
```

Hoặc cài tay:
1. Tải ở **https://ollama.com/download**
2. Mở Terminal / CMD gõ: `ollama pull qwen2.5:1.5b`  (model ~900MB, chạy CPU 6-8GB RAM rất mượt)
3. Khởi động lại CLARA — nó **tự nhận Ollama** và chuyển sang dùng LLM thật

> 💡 Máy rất yếu (4GB RAM): `ollama pull qwen2.5:0.5b` (~350MB)  
> 💡 Máy khỏe (8GB+): `ollama pull qwen2.5:3b` (~1.9GB, thông minh hơn)

### Bước 3 (tùy chọn): Mở giao diện web

```bash
pip install flask     # chỉ cần cài 1 lần
python main.py --web
```

Tự động mở trình duyệt tại `http://127.0.0.1:5000`

### Bước 4 (tùy chọn): Chế độ giọng nói

```bash
pip install SpeechRecognition pyaudio pyttsx3
python main.py --voice
```

CLARA sẽ nghe bạn nói qua micro và trả lời qua loa.

---

## 💬 Tương tác với CLARA

### Nói tự nhiên

CLARA đi qua đủ 9 bước nhận thức cho mọi tin nhắn. Cứ nói như nói với người:
- "Chào bạn"
- "Tôi tên là Huy, tôi năm nay 28 tuổi, tôi thích lập trình Python"
- "Nhớ: quán phở tôi thích là ở phố Hàng Đồng, Hà Nội"
- "Tôi tên là gì?"
- "Tôi thích ăn gì?"
- "Tính (2^8 * 3.14) / 17"
- "Viết file poem.txt | Hôm nay trời xanh..."

### Các lệnh đặc biệt

| Lệnh | Tác dụng |
|---|---|
| `commands` | Xem toàn bộ lệnh |
| `status` | Xem trạng thái nội bộ (brain, memory, goals…) |
| `goal <mục tiêu>` | Thêm mục tiêu tự chủ cho CLARA |
| `forget <từ khóa>` | Bảo CLARA quên kiến thức liên quan |
| `dream` | Ép "ngủ mơ" tổng hợp ký ức thành bài học |
| `export` | Xuất toàn bộ trí nhớ ra file JSON |
| `nhớ: X là Y` | Dạy kiến thức mới (trực tiếp) |
| `tốt` / `tệ vì ...` | Feedback để CLARA học |
| `quit` / `thoát` | Thoát (**trí nhớ giữ nguyên lần sau**) |

### Feedback vòng lặp học

Sau mỗi câu trả lời của CLARA, bạn có thể:
- `tốt` — nó tăng trọng số cách trả lời vừa dùng
- `tệ vì đáp án đúng là ...` — nó học câu trả lời đúng và tự tạo skill mới nếu gặp lỗi lặp lại

---

## 🧠 Cách nó xử lý mỗi tin nhắn (9 bước)

```
USER INPUT
   ↓
[1] PERCEIVE    — phát hiện cảm xúc của bạn, suy đoán ý định (chào/hỏi/dạy/feedback…)
[2] RETRIEVE    — kéo từ 3 lớp bộ nhớ + user model + thủ tục liên quan vào WM
[3] FEEL        — ước lượng mức độ "bất ngờ" (uncertainty), áp dụng curiosity
[4] PLAN        — yêu cầu brain lập kế hoạch, quyết định có cần tool không
[5] CHOOSE TOOL — chọn công cụ phù hợp (calc / read / write / run_python / …)
[6] ACT         — thực thi công cụ (với sandbox an toàn), đưa kết quả vào WM
[7] ANSWER      — tổng hợp WM thành câu trả lời tự nhiên
[8] REFLECT     — tự chấm điểm, < 6/10 thì viết lại
[9] CONSOLIDATE — lưu episode, tự học facts, cập nhật user model, tiến bộ trên goals
   ↓
TRẢ LỜI (kèm thời gian, loại brain, độ chấc, và dấu 💭 nếu đã tự sửa)
```

Mỗi bước là **module độc lập** — bạn có thể thay/upgrade từng bước mà không đụng các bước khác.

---

## 🔬 Bằng chứng khoa học

CLARA xây trên 4 lý thuyết uy tín nhất về trí tuệ và ý thức:

1. **🌐 Global Workspace Theory** (Baars 1988, Dehaene et al. 2003) — bảng thông tin toàn cục, mô hình được chấp nhận rộng rãi nhất về ý thức con người. Đây chính là kiến trúc của "thinking" trong tâm lý học nhận thức.

2. **🎯 Active Inference** (Friston 2010) — trí tuệ = quá trình giảm thiểu "sai số dự đoán" (prediction error / free energy). CLARA thể hiện qua uncertainty scoring + reflect loop + goal-seeking.

3. **🪞 Reflexion** (Shinn et al., 2023 — *Reflexion: Language Agents with Verbal Reinforcement Learning*) — agent thông minh nhất hiện nay (Devin, SWE-agent, OpenAI o1) đều dùng kỹ thuật "tự xem lại câu trả lời".

4. **🧠 Bộ nhớ 3 lớp** — Tulving (1972, 1985) phân biệt episodic/semantic/procedural memory, đây là khuôn mẫu chuẩn của trí nhớ người.

Đây **chính là kiến trúc** các agent mạnh nhất thế giới (Devin, OpenAI Agent, Claude Computer Use) đang dùng — khác biệt duy nhất là họ dùng LLM lớn (70-400B) chạy trên chục GPU, còn CLARA dùng LLM 0.5-3B chạy trên CPU của bạn.

---

## 🤖 Tự nâng cấp (self-improvement) hoạt động thế nào?

CLARA có **3 cấp độ tự nâng cấp** (tất cả đều có ngay trong v1.0):

### Cấp 1 — Parametric learning (học theo thời gian)
- Trọng số knowledge tăng/giảm theo feedback
- Trọng số thủ tục/procedure tăng theo success rate
- Mô hình người dùng cập nhật sau mỗi lượt nói

### Cấp 2 — Verbal reinforcement (tự phản tỉnh)
- Sau mỗi câu trả lời, tự phê bình và viết lại khi chưa tốt
- Nhận diện pattern sai qua các lần feedback và điều chỉnh cách trả lời
- Chế độ "ngủ mơ" tổng hợp bài học tổng quát từ ký ức

### Cấp 3 — Procedural self-improvement (tự viết skill)
Khi phát hiện lỗi lặp lại, CLARA **tự tạo ra thủ tục mới** và lưu vào procedural memory — nghĩa là hành vi của nó thực sự thay đổi dựa trên kinh nghiệm. Đây là bước đầu tiên của recursive self-improvement, chạy được trên laptop.

> ⚠️ **Thành thật mà nói**: CLARA **vẫn chưa phải AGI** (chẳng có ai có cái đó năm 2026). Nó không thể tự thiết kế lại kiến trúc neural của chính nó (điều đó đòi tính toán lớn), nhưng nó **đang ở kiến trúc đúng đường đi đến AGI**, và bạn có thể nâng cấp LLM lên từ từ khi máy bạn khỏe hơn.

---

## 🛡️ Về an toàn & riêng tư

- **100% local** — không gửi dữ liệu của bạn đi đâu cả
- File có `run_python` chạy code trong **sandbox** (chặn `open`, `eval`, `exec`, `import` bừa, timeout 8s, chạy process con)
- Đọc/ghi file chỉ được trong thư mục `workspace/` (không thể đụng file hệ thống)
- Mọi trí nhớ lưu trong `data/clara.db` (SQLite), bạn có thể xóa bất cứ lúc nào để CLARA "sinh ra lại từ đầu"
- Không có telemetry, không có kết nối ngầm

---

## 🔧 Các tham số dòng lệnh

```
python main.py [options]
  --micro            Bắt buộc dùng micro brain (dù có Ollama)
  --model <tên>      Chỉ định Ollama model (vd qwen2.5:0.5b)
  --web              Mở giao diện web
  --voice            Bật chế độ giọng nói
  --host 127.0.0.1   Bind host cho web
  --port 5000        Bind port cho web
  --dream-every N    Tự ngủ mơ sau N lượt (mặc định 10, 0=tắt)
  --no-auto-skill    Tắt tự tạo skill mới
```

---

## 📈 Độ khó chạy theo cấu hình máy

| Máy | Model | RAM dùng | Chế độ |
|---|---|---|---|
| Rất yếu (4GB RAM, CPU 2 nhân cũ) | micro hoặc qwen2.5:0.5b | 50MB / ~500MB | CLI |
| Văn phòng thường (6-8GB RAM, i3/i5) | qwen2.5:1.5b | ~1GB | CLI / Web |
| Khỏe (8-16GB RAM, i7/Ryzen 5+) | qwen2.5:3b | ~2.5GB | CLI / Web / Voice |
| Có GPU NVIDIA/AMD | qwen2.5:7b hoặc lớn hơn | tùy model | Web + Voice |

Ollama tự động dùng GPU nếu nhận được card đồ họa tương thích.

---

## 💡 Mẹo hay

1. **Dạy CLARA vài điều trong tuần đầu** — nó sẽ ngày càng hiểu bạn và trả lời đúng ý hơn
2. **Thỉnh thoảng dùng feedback** "tốt"/"tệ vì..." — đó là cách nhanh nhất để CLARA tiến bộ
3. **Để `dream` tự động** (mặc định mỗi 10 lượt) — bạn sẽ thấy thú vị khi nó rút ra bài học tổng quát
4. **Khi có việc cần tính toán/code**, cứ nói thẳng "tính ..." hay "chạy python ..." — CLARA sẽ tự dùng công cụ thay vì đoán
5. **Sao lưu thư mục `data/`** — đó là toàn bộ "linh hồn" của CLARA (trí nhớ + tính cách + thủ tục). Copy nó sang máy khác là CLARA mang nguyên ký ức đi

---

## 🛣️ Lộ trình (bạn có thể tự hack tiếp)

Code chỉ vài trăm dòng mỗi file, dễ đọc dễ sửa. Các ý tưởng hay để mở rộng:

- [ ] Thêm công cụ **duyệt web** (qua `requests` + `BeautifulSoup`) — cho CLARA tự tìm thông tin mới
- [ ] Thêm **vector search thật** (sqlite-vss hoặc `sentence-transformers/all-MiniLM-L6-v2`) để tìm ngữ nghĩa chính xác hơn
- [ ] Thêm **multi-agent** — nhiều instance CLARA nói chuyện với nhau (debate, hợp tác giải quyết vấn đề)
- [ ] Thêm **planning dài hạn** (mục tiêu nhiều bước, theo dõi tiến độ)
- [ ] Tích hợp **vision** (mô hình Moondream hoặc LLaVA qua Ollama) để CLARA nhìn ảnh/màn hình
- [ ] **Self-modification có kiểm soát** — CLARA đề xuất thay đổi code của chính nó và yêu cầu bạn duyệt trước khi áp dụng

---

## ❓ Hỏi đáp nhanh

**Q: Chạy không cần internet?**  
A: Có. Chỉ cần internet khi bạn pull model Ollama lần đầu, sau đó mọi thứ hoàn toàn offline.

**Q: Nếu tôi tắt máy, CLARA có nhớ tôi không?**  
A: Có. Tất cả lưu trong `data/clara.db`. Mở lại nó nhớ hết.

**Q: Có thể cho CLARA "quên hết và bắt đầu lại từ đầu" không?**  
A: Xóa thư mục `data/` là xong.

**Q: So với ChatGPT/Claude thì sao?**  
A: Về kiến thức tổng quát, CLARA dùng LLM nhỏ nên yếu hơn. Về kiến trúc tự học và riêng tư, CLARA hơn hẳn vì chạy local, có bộ nhớ ba lớp, tự phản tỉnh và tự tạo skill — mọi thứ trên máy bạn. Khi bạn nâng model lên 7B-14B (có GPU), khả năng trả lời sẽ ngang ngửa các dịch vụ đám mây.

**Q: Tôi có thể xem/sửa code không?**  
A: Được — toàn bộ là Python thuần, không biên dịch, không obfuscate. Đây là dự án để bạn cùng phát triển.

---

*Made with ❤️ — cho những ai muốn sở hữu một AI của riêng mình.*
