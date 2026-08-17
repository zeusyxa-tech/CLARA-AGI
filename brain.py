"""
CLARA-AGI v1.4 - Brain abstraction.
Hỗ trợ: Ollama local (tự nhận), fallback là MicroLLM (template, chạy được mọi máy).
"""
import json, urllib.request, re, time, os, hashlib, unicodedata
from pathlib import Path
from prompts_vi import system_for, language_name, normalize_language

DEFAULT_OLLAMA = "qwen2.5:1.5b"
CANDIDATE_MODELS = [
    "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b",
    "phi3.5:mini", "gemma2:2b", "tinyllama", "llama3.2:1b", "llama3.2:3b",
    "mistral:7b",
]
OLLAMA_URL = os.environ.get("CLARA_OLLAMA_URL", "http://localhost:11434")
OPENAI_API_BASE = (os.environ.get("OPENAI_API_BASE") or "").rstrip("/") or f"{OLLAMA_URL}/v1"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")


# ---------------- OLLAMA ----------------
def ollama_list(url=OLLAMA_URL):
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=1.5) as r:
            return json.loads(r.read()).get("models", [])
    except Exception:
        return None


def ollama_chat(prompt, model=DEFAULT_OLLAMA, url=OLLAMA_URL, temperature=0.5, num_predict=400):
    data = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "top_p": 0.9, "seed": -1}
    }).encode()
    req = urllib.request.Request(f"{url}/api/generate", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        j = json.loads(resp.read())
    return (j.get("response") or "").strip()


def ollama_chat_messages(messages, model=DEFAULT_OLLAMA, url=OLLAMA_URL, temperature=0.5, num_predict=400):
    data = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "top_p": 0.9, "seed": -1}
    }).encode()
    req = urllib.request.Request(f"{url}/api/chat", data=data,
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    try:
        j = json.loads(resp.read())
    finally:
        close = getattr(resp, "close", None)
        if callable(close):
            close()
    msg = j.get("message") or {}
    if not msg:
        choice = (((j.get("choices") or [{}])[0]).get("message") or {})
        msg = choice
    content = (msg.get("content") or "").strip()
    return content if content is not None else ""


# ---------------- OPENAI-COMPATIBLE ----------------
def openai_chat(prompt, model=DEFAULT_OLLAMA, base_url=OPENAI_API_BASE, api_key=OPENAI_API_KEY,
                temperature=0.5, num_predict=400):
    url = f"{base_url}/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": num_predict,
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={
                                     "Content-Type": "application/json",
                                     "Authorization": f"Bearer {api_key}",
                                 })
    with urllib.request.urlopen(req, timeout=120) as resp:
        j = json.loads(resp.read())
    choice = (((j.get("choices") or [{}])[0]).get("message") or {})
    return (choice.get("content") or "").strip()


# ---------------- COMMON POST ----------------
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_think(text: str) -> str:
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


# ---------------- TASK TAGS ----------------
T_PLAN    = "__PLAN__"
T_TOOL    = "__TOOL__"
T_REFLECT = "__REFLECT__"
T_REWRITE = "__REWRITE__"
T_ANSWER  = "__ANSWER__"
T_SKILL   = "__SKILL__"
T_DREAM   = "__DREAM__"


# ---------------- MICRO FALLBACK ----------------
class MicroLLM:
    """Template brain không cần mạng. Đủ thông minh cho demo & test kiến trúc."""
    name = "micro"

    def think(self, tag, prompt, **kw):
        if tag == T_PLAN:    return self._plan(prompt)
        if tag == T_TOOL:    return self._tool(prompt)
        if tag == T_REFLECT: return self._reflect(prompt)
        if tag == T_REWRITE: return self._rewrite(prompt)
        if tag == T_SKILL:   return self._skill(prompt)
        if tag == T_DREAM:   return self._dream(prompt)
        return self._answer(prompt)

    # ---------- ANSWER ----------
    def _wm(self, prompt):
        """Trích mảng working memory từ prompt (list các dict)."""
        m = re.search(r"\[WORKSPACE\](.*?)\[/WORKSPACE\]", prompt, re.S)
        if not m: return []
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            return []

    def _user_msg(self, wm):
        for it in wm:
            if it.get("role") == "user":
                return it.get("content", "")
        return ""

    def _sem_hits(self, wm):
        for it in wm:
            if it.get("role") == "semantic_hits":
                return it.get("content") or []
        return []

    def _tool_result(self, prompt):
        m = re.search(r"\[TOOL_RESULT\](.*?)\[/TOOL_RESULT\]", prompt, re.S)
        return m.group(1).strip() if m else ""

    def _answer(self, prompt):
        wm = self._wm(prompt)
        user_msg = self._user_msg(wm) or prompt
        low = user_msg.lower().strip()
        sem = self._sem_hits(wm)
        tr = self._tool_result(prompt)

        # câu hỏi về chính người dùng
        user_q_re = re.compile(
            r"tên tôi|tôi tên|tôi tên gì|tôi bao nhiêu tuổi|tuổi tôi|"
            r"tôi thích gì|tôi ghét gì|tôi làm nghề gì|tôi ở đâu|"
            r"bạn còn nhớ tôi|bạn biết gì về tôi|tôi là ai|tôi là gì|"
            r"tôi sinh năm|tôi năm sinh|tôi bao nhiêu|tên của tôi",
            re.I,
        )
        if user_q_re.search(low):
            um = {}
            for it in wm:
                if it.get("role") == "user_model":
                    raw = it.get("content") or {}
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except Exception:
                            raw = {}
                    um = raw
                    break
            if um:
                parts = []
                for k, v in um.items():
                    parts.append(f"{k}: {v}")
                return "Bạn có các thông tin: " + ", ".join(parts) + "."
            return "Tôi chưa biết rõ về bạn lắm. Bạn có thể cho tôi biết thêm không?"

        # chào
        if re.match(r"^(chào|hello|hi|xin chào|hey)\b", low):
            return "Chào bạn! Tôi là CLARA-AGI v1.4. Rất vui được trò chuyện với bạn."
        # hỏi danh tính CLARA
        if "bạn" in low and ("ai" in low or "là gì" in low or "tên gì" in low or "giới thiệu" in low):
            return ("Tôi là CLARA-AGI v1.4 — một tác nhân tự chủ có kiến trúc gần AGI "
                    "(bộ nhớ 3 lớp, không gian làm việc toàn cục, tự phản tỉnh, dùng công cụ, tự tạo skill). "
                    "Tôi chạy hoàn toàn local trên máy bạn.")
        if re.search(r"(mấy giờ|giờ gì|ngày mấy|hôm nay)", low):
            return f"🕒 Bây giờ là {time.strftime('%H:%M:%S ngày %d/%m/%Y')}."
        if re.search(r"(cảm ơn|thank|thanks)", low):
            return "Không có gì! 😊"
        if "help" in low or "trợ giúp" in low or "giúp" == low.strip():
            return ("Bạn có thể hỏi tôi, bảo tôi tính toán, đọc/ghi file, chạy code Python, "
                    "dạy tôi bằng 'nhớ: ...', hoặc feedback 'tốt/tệ' để tôi học. "
                    "Gõ 'commands' để xem toàn bộ lệnh.")

        # có kết quả công cụ
        if tr and tr != "không dùng" and not tr.startswith("không dùng"):
            if "❌" in tr[:50] or "Lỗi" in tr[:50]:
                return f"Công cụ báo lỗi: {tr}"
            return f"Kết quả từ công cụ:\n{tr}"

        # có semantic hits
        if sem:
            # chọn ra cái liên quan nhất (heuristic: nhiều từ trùng)
            qw = set(self._tok(low))
            best, bs = sem[0], 0
            for s in sem:
                sw = set(self._tok(s))
                sc = len(qw & sw)
                if sc > bs:
                    bs, best = sc, s
            return f"Theo những gì tôi đã học: {best}" + ("." if not best.endswith(".") else "")

        # "nhớ: ..."
        m = re.match(r"^(nhớ|ghi nhớ|note|học)\s*[:\-]?\s*(.+)$", user_msg, re.I)
        if m:
            return f"✅ Đã ghi nhớ: '{m.group(2).strip()}'."

        # câu hỏi
        if user_msg.endswith("?") or any(low.startswith(k) for k in ["tại sao","vì sao","làm sao","như thế nào","gì","ai","ở đâu","bao nhiêu"]):
            return ("Tôi chưa đủ dữ liệu để trả lời chắc. Bạn hãy dạy tôi bằng 'nhớ: ...', "
                    "hoặc cài Ollama + qwen2.5:1.5b để tôi có khả năng suy luận thật.")

        # nhận thông tin / mệnh đề
        if re.search(r"tôi\s+(?:thích|ghét|hay\s+(?:uống|ăn|chơi|đọc|xem|nghe)|yêu|thường|đam\s+mê)\s+.+", user_msg, re.I):
            return f"Đã ghi nhận: '{user_msg}'. Lưu vào semantic memory."

        return f"Đã nghe: '{user_msg[:80]}'. Tôi lưu vào episodic memory."

    # ---------- PLAN ----------
    def _plan(self, prompt):
        wm = self._wm(prompt)
        user_msg = self._user_msg(wm)
        low = user_msg.lower()
        tool = "none"
        # phát hiện intent
        if re.search(r"\d\s*[\+\-\*\/\^]\s*\d", user_msg) or re.search(r"(tính|calculate)\b", low) or "math." in user_msg or re.search(r"sqrt\(|sin\(|cos\(|log\(|pi\b|exp\(", user_msg):
            # lấy biểu thức: sau "tính" hoặc cả dòng
            m_after = re.search(r"(?:tính|calculate)\s+(.+)", user_msg, re.I)
            expr = m_after.group(1).strip().rstrip("?.!") if m_after else user_msg.strip().rstrip("?.!")
            expr_clean = re.sub(r"\s+", "", expr)
            if re.search(r"[\d\(]", expr_clean) and (re.search(r"[\+\-\*\/\^%]", expr_clean) or "math." in expr_clean or "sqrt(" in expr_clean):
                tool = f"calc {expr}"
            else:
                tool = "none"
        elif re.search(r"(mấy giờ|giờ gì|ngày mấy|hôm nay|bây giờ)", low):
            tool = "now"
        elif re.search(r"(đọc|mở|xem)\s+(file|tệp|nội dung)?", low):
            m = re.search(r"(?:đọc|mở|xem)\s+(?:file|tệp|nội dung)?\s*([^\s\?\!]+)?", low)
            path = (m.group(1) if m and m.group(1) else ".").strip()
            if path in ("", "."):
                # thử lấy path theo kiểu "đọc file <tên>" (cả phần có .)
                m2 = re.search(r"(?:đọc|mở|xem)\s+(?:file|tệp|nội dung)?\s+(\S+)", user_msg)
                path = m2.group(1).rstrip("?.!") if m2 else "."
            tool = f"read {path}"
        elif re.search(r"(liệt kê|ls|xem thư mục|danh sách file)", low):
            tool = "list ."
        elif re.search(r"(ghi|viết|lưu|tạo)\s+(file|tệp|vào|ra)", low):
            m = re.search(r"(?:ghi|viết|lưu|tạo)\s+(?:file|tệp|vào|ra)\s+([^\|]+)\|\s*([\s\S]+)$", user_msg, re.I)
            if m:
                path = m.group(1).strip().rstrip()
                content = m.group(2).strip()
                tool = f"write {path}|{content[:300]}"
            else:
                tool = "none"
        elif re.search(r"(chạy|run|thực thi)\s+(python|code|chương trình|script)", low) or "```python" in user_msg:
            code = ""
            if "```python" in user_msg:
                cm = re.search(r"```python\s*(.*?)\s*```", user_msg, re.S)
                code = cm.group(1).strip() if cm else ""
            else:
                # chấp nhận: "chạy python: code" | "chạy python | code" | "chạy python\ncode"
                cm = re.search(r"(?:chạy|run|thực thi)\s+(?:python|code|script)\s*[:\|]?\s*\n?([\s\S]+)", user_msg, re.I)
                if cm:
                    code = cm.group(1).strip()
                    # nếu sau dấu | thì lấy phần sau
                    if "|" in code[:20]:
                        code = code.split("|", 1)[1].strip()
            if code:
                tool = f"run_python {code[:300]}"
            else:
                tool = "none"
        elif re.search(r"(tìm|kiếm|search|grep)\s", low) or re.search(r"(nhớ gì|biết gì)", low):
            q = re.sub(r"^(tìm|kiếm|search|bạn\s+nhớ\s+gì\s+về)\s*", "", low)
            tool = f"search {q[:60]}"
        steps = ["Phân tích yêu cầu","Truy xuất bộ nhớ"]
        if tool != "none":
            steps.append(f"Dùng công cụ {tool.split()[0]}")
        steps += ["Tổng hợp câu trả lời","Tự phản tỉnh","Trả lời người dùng"]
        needs = tool != "none"
        return json.dumps({"steps": steps, "needs_tool": needs, "tool_name": tool.split()[0], "tool_args": tool}, ensure_ascii=False)

    # ---------- TOOL ----------
    def _tool(self, prompt):
        # đã có sẵn tool_name từ plan trong prompt → trích
        m = re.search(r'"tool_args"\s*:\s*"([^"]+)"', prompt)
        if m:
            return m.group(1)
        # fallback dựa vào từ khóa
        low = prompt.lower()
        if "tính" in low or re.search(r"\d\s*[\+\-\*\/]\s*\d", prompt):
            expr = re.search(r"\d[\d\s\.\+\-\*\/\(\)\^%]*", prompt)
            if expr: return f"calc {expr.group(0).strip()}"
        if "giờ" in low: return "now"
        return "none"

    # ---------- REFLECT ----------
    def _reflect(self, prompt):
        issues = []
        ans_m = re.search(r"\[ANSWER\](.*?)\[/ANSWER\]", prompt, re.S)
        ans = ans_m.group(1) if ans_m else prompt
        if len(ans) < 30: issues.append("- Câu trả lời quá ngắn, có thể thiếu thông tin.")
        if "?" in ans[-60:]: issues.append("- Phần cuối là câu hỏi, tránh hỏi lại người dùng.")
        if "không biết" in ans.lower() or "chưa có đủ" in ans.lower():
            issues.append("- Tôi đang nói 'không biết' — nếu có công cụ phù hợp nên dùng.")
        if "tôi là clara" in ans.lower() and "tôi tên" not in prompt.lower() and "bạn là ai" not in prompt.lower():
            issues.append("- Tôi tự giới thiệu dù người dùng không hỏi.")
        if not issues:
            issues.append("- Câu trả lời chấp nhận được.")
        issues.append("- Nên ngắn gọn, bám sát thông tin từ bộ nhớ/công cụ.")
        score = max(3, 8 - len(issues))
        return "Phê bình:\n" + "\n".join(issues) + f"\nĐiểm: {score}/10"

    # ---------- REWRITE ----------
    def _rewrite(self, prompt):
        m_ans = re.search(r"\[ANSWER\](.*?)\[/ANSWER\]", prompt, re.S)
        m_cri = re.search(r"\[CRITIQUE\](.*?)\[/CRITIQUE\]", prompt, re.S)
        ans = m_ans.group(1).strip() if m_ans else prompt
        cri = m_cri.group(1) if m_cri else ""
        # Heuristic rewrite: cắt bớt phần thừa
        lines = [l for l in ans.split("\n") if l.strip()]
        if lines:
            first = lines[0].strip()
            if "tôi là clara" in first.lower() and "bạn là ai" not in prompt.lower() and "giới thiệu" not in prompt.lower():
                # nếu không hỏi về bản thân thì trả lời dựa trên thông tin người dùng
                wm = self._wm(prompt)
                sem = self._sem_hits(wm)
                if sem:
                    return f"Theo những gì tôi đã học: {sem[0]}."
                return "Tôi đã nghe rồi và ghi nhớ điều bạn nói."
            return "\n".join(lines[:3])
        return ans

    # ---------- SKILL (tự tạo procedure) ----------
    def _skill(self, prompt):
        # tìm câu hỏi/mistake
        m = re.search(r"\[MISTAKE\](.*?)\[/MISTAKE\]", prompt, re.S)
        mistake = m.group(1).strip() if m else prompt
        # tạo tên skill
        words = re.findall(r"[a-zà-ỹA-ZÀ-Ỵ]+", mistake.lower())
        stop = {"tôi","bạn","là","và","của","có","trong","với","đã","sẽ","này","kia","vì","rất"}
        keys = [w for w in words if w not in stop][:3]
        name = "handle_" + "_".join(keys or ["unknown"])[:40]
        steps = [
            "Phát hiện trường hợp tương tự.",
            f"Phân tích lỗi: {mistake[:100]}",
            "Suy nghĩ các cách xử lý đúng.",
            "Kiểm tra lại với bộ nhớ/công cụ.",
            "Trả lời một cách thận trọng."
        ]
        return json.dumps({
            "name": name,
            "description": f"Tự động xử lý khi gặp tình huống liên quan đến: {mistake[:60]}",
            "steps": steps
        }, ensure_ascii=False)

    # ---------- DREAM (tổng hợp khi rảnh) ----------
    def _dream(self, prompt):
        # rút ra vài bài học tổng quát từ dữ liệu
        m = re.search(r"\[EPISODES\](.*?)\[/EPISODES\]", prompt, re.S)
        eps = m.group(1) if m else ""
        lessons = []
        if "tệ" in eps.lower() or "sai" in eps.lower():
            lessons.append("Khi người dùng nói 'tệ/sai', tôi nên cảm ơn và hỏi cách sửa tốt hơn thay vì xin lỗi quá nhiều.")
        if "?" in eps[-500:]:
            lessons.append("Khi người dùng hỏi câu mở, tôi nên dựa vào bộ nhớ đã học trước khi đoán.")
        if not lessons:
            lessons.append("Tiếp tục ghi nhớ sở thích & thông tin người dùng chia sẻ.")
        summary = f"Tổng hợp từ {len(eps.splitlines())} dòng ký ức."
        return json.dumps({"summary": summary, "lessons": lessons}, ensure_ascii=False)

    def _tok(self, s):
        return [w for w in re.split(r"\W+", s.lower()) if len(w) > 1]


# ---------------- BRAIN CHUNG ----------------
class Brain:
    def __init__(self, force_micro=False, model=None, language=None):
        self.models = ollama_list()
        self.backend = "micro"
        self.model = model or DEFAULT_OLLAMA
        self.micro = MicroLLM()
        self.temperature = 0.5
        self.language = normalize_language(language or os.environ.get("CLARA_LANGUAGE"), default="vi")
        if not force_micro and self.models is not None:
            names = [m.get("name","") for m in self.models]
            for cand in [self.model] + CANDIDATE_MODELS:
                if any(cand in n or n.startswith(cand.split(":")[0]+":") for n in names):
                    self.model = cand
                    self.backend = "ollama"
                    break

    def think(self, tag, prompt, **kw):
        t = kw.get("temperature", self.temperature)
        sys_prompt = self._tag_to_system(tag)
        if self.backend == "ollama":
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ]
            try:
                out = ollama_chat_messages(messages, model=self.model, temperature=t,
                                           num_predict=kw.get("num_predict", 400)) or ""
            except Exception:
                out = ""
            if not out:
                try:
                    out = ollama_chat(f"{sys_prompt}\n{prompt}", model=self.model, temperature=t,
                                      num_predict=kw.get("num_predict", 400))
                except Exception as e:
                    out = f"[ollama lỗi: {e}]\n"
        elif self.backend == "openai":
            full = f"{sys_prompt}\n{prompt}"
            try:
                out = openai_chat(full, model=self.model, temperature=t,
                                  num_predict=kw.get("num_predict", 400))
            except Exception as e:
                out = f"[openai lỗi: {e}]\n"
        else:
            out = ""
        out = strip_think(out)
        if out and len(out.strip()) > 2:
            return out.strip()
        return self.micro.think(tag, prompt)

    def _tag_to_system(self, tag):
        return system_for(tag, language=self.language)

    def status(self):
        return {"backend": self.backend,
                "model": self.model if self.backend == "ollama" else "micro-template",
                "available_models": [m.get("name") for m in (self.models or [])][:10],
                "language": getattr(self, "language", "vi")}
