"""
CLARA-AGI v1.2 / Self-Improvement Agent Loop
Chạy song song với curriculum + autolearn, quyết định cải thiện theo dữ liệu thật.
"""
import time, random, json, threading, re
from pathlib import Path


class SelfImprovementLoop:
    def __init__(self, agi, interval=360, verbose=True):
        self.agi = agi
        self.interval = interval
        self.verbose = verbose
        self._running = False
        self._thread = None
        self.steps_done = 0
        self.stats = {"audit": 0, "weak_patch": 0, "self_eval": 0, "research_gap": 0}

    # ------------------ điều khiển ------------------
    def start(self):
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
        return {"running": self._running, "interval": self.interval,
                "steps_done": self.steps_done, "stats": self.stats}

    # ------------------ loop chính ------------------
    def _loop(self):
        time.sleep(15)
        while self._running:
            try:
                self._one_step()
            except Exception as e:
                if self.verbose:
                    print(f"[self-improve] err: {e}", flush=True)
            for _ in range(int(self.interval)):
                if not self._running:
                    return
                time.sleep(1)

    def _log(self, msg):
        if self.verbose:
            t = time.strftime("%H:%M:%S")
            print(f"\r🧩 [{t}] self-improve: {msg}", flush=True)

    # ------------------ 1 bước ------------------
    def _one_step(self):
        self.steps_done += 1
        choice = random.choices(
            ["audit", "weak_patch", "self_eval", "research_gap"],
            weights=[0.40, 0.25, 0.20, 0.15],
            k=1,
        )[0]

        if choice == "audit":
            self._act_audit()
        elif choice == "weak_patch":
            self._act_weak_patch()
        elif choice == "self_eval":
            self._act_self_eval()
        elif choice == "research_gap":
            self._act_research_gap()

    # ------------------ audit bộ nhớ/goals ------------------
    def _act_audit(self):
        self.stats["audit"] += 1
        goals = self.agi.mem.get_active_goals(20)
        topic_counts = {}
        for row in self.agi.mem.conn.execute(
            "SELECT topic, count FROM topic_history ORDER BY last_picked DESC"
        ).fetchall():
            topic_counts[row[0]] = topic_counts.get(row[0], 0) + row[1]

        stale_topics = [t for t, c in topic_counts.items() if c >= 3]
        weak_goals = [g["goal"] for g in goals if g.get("priority", 0) >= 0.7]

        if weak_goals:
            target = random.choice(weak_goals)
            self._log(f"mục tiêu yếu: {target[:60]}...")
            self._auto_improve_topic(target)
        elif stale_topics:
            target = random.choice(stale_topics)
            self._log(f"chủ đề lặp: {target[:60]}...")
            self._auto_improve_topic(target)
        else:
            self._log("audit sạch, chưa cần vá")

    # ------------------ vá điểm yếu đã biết ------------------
    def _act_weak_patch(self):
        self.stats["weak_patch"] += 1
        bad = list(self.agi.mem.conn.execute(
            "SELECT content FROM episodes WHERE kind='mistake' OR kind='self_qa_mistake' "
            "ORDER BY ts DESC LIMIT 10"
        ).fetchall())
        if not bad:
            self._log("không thấy mistake cần vá")
            return

        mistake = random.choice(bad)[0][:400]
        prompt = (
            "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n"
            "Đây là một lỗi/kết quả tệ của chính tôi:\n"
            f"{mistake}\n\n"
            "Hãy đặt cho tôi MỘT chủ đề nghiên cứu ngắn gọn (1 câu tiếng Việt) để khắc phục lỗi này."
        )
        topic = self.agi.brain.think(
            self.agi.brain.T_ANSWER if hasattr(self.agi.brain, "T_ANSWER") else "__ANSWER__",
            prompt,
            temperature=0.5,
        )
        topic = self._clean(topic)
        if topic:
            self._log(f"chủ đề vá lỗi: {topic[:60]}...")
            self._auto_improve_topic(topic)

    # ------------------ tự kiểm tra kỹ năng active ------------------
    def _act_self_eval(self):
        self.stats["self_eval"] += 1

        if self.agi.brain.status().get("backend") == "micro":
            self._log("micro brain — bỏ qua đánh giá skill bằng LLM")
            return

        try:
            from self_improve import list_active
            skills = [s["file"] for s in list_active()]
        except Exception:
            skills = []

        if not skills:
            self._log("chưa có skill active để đánh giá")
            return

        skill = random.choice(skills)
        prompt = (
            "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n"
            f"Hãy tự kiểm tra skill '{skill}' của tôi. "
            "Trả về JSON duy nhất: {\"ok\": bool, \"score\": float 0-1, \"issue\": str}."
        )
        raw = self.agi.brain.think(
            self.agi.brain.T_REFLECT if hasattr(self.agi.brain, "T_REFLECT") else "__ANSWER__",
            prompt,
            temperature=0.2,
        )
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else {}
        except Exception:
            data = {}

        score = float(data.get("score", 0.0) or 0.0)
        issue = str(data.get("issue", ""))[:120]
        if data.get("ok") and score >= 0.8:
            self._log(f"skill {skill} ổn ({score:.2f})")
        else:
            self._log(f"skill {skill} điểm thấp ({score:.2f}) — {issue}")
            topic = f"cải thiện skill {Path(skill).stem}: {issue or 'tối ưu logic'}"
            self._auto_improve_topic(topic)

    def _act_research_gap(self):
        self.stats["research_gap"] += 1
        count = self.agi.mem.conn.execute(
            "SELECT count(*) FROM semantics WHERE confidence < 0.5"
        ).fetchone()[0]
        if count == 0:
            self._log("không thấy knowledge gap nghiêm trọng")
            return

        row = self.agi.mem.conn.execute(
            "SELECT fact FROM semantics WHERE confidence < 0.5 ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        topic = row[0] if row else "kiến thức đang mơ hồ"
        self._log(f"knowledge gap: {topic[:60]}...")
        self._auto_improve_topic(topic)

    # ------------------ helper ------------------
    def _auto_improve_topic(self, topic: str):
        # Luôn học gì đó trước
        try:
            from self_improve import research
            research(self.agi, topic, max_pages=1)
        except Exception as e:
            self._log(f"research err: {e}")

        # Compliance check before skill proposal
        try:
            from compliance import compliance_report, load_owner_policy
            report = compliance_report(topic, load_owner_policy())
            if not report["legit_income"] or not report["owner_aligned"]:
                self._log(f"skip non-compliant topic: {topic}")
                return
        except Exception:
            pass

        # Cố đề xuất skill nếu model đủ mạnh
        tried_skill = False
        try:
            from self_improve import propose_skill
            prop = propose_skill(self.agi, topic)
            if prop.get("ok"):
                tried_skill = True
                self.stats["weak_patch"] += 1
                self._log(f"skill đề xuất: {prop['name']}")
        except Exception:
            pass

        if not tried_skill:
            self._fallback_mini_procedure(topic)

    def _fallback_mini_procedure(self, topic: str):
        try:
            import unicodedata
            slug = unicodedata.normalize("NFD", topic.lower())
            slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")
            slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")[:20].strip("_") or "auto_proc"
            name = f"{slug}_{abs(hash(topic)) % 1000}"[:32]
            existing = [r[0] for r in self.agi.mem.conn.execute(
                "SELECT name FROM procedures WHERE name=?", (name,)
            ).fetchall()]
            if existing:
                return
            steps = [
                f"Xác định yếu tố cốt lõi của chủ đề: {topic}",
                f"Áp dụng '{topic}' vào ví dụ an toàn, có thể kiểm chứng kết quả",
                "Nếu có lỗi/phản hồi tiêu cực, sửa lại bước 2 rồi ghi nhớ pattern",
            ]
            self.agi.mem.add_procedure(
                name,
                f"Mini thủ tục tự tạo cho: {topic}",
                steps,
                success_rate=0.55,
                auto_created=True,
            )
            self.agi.mem.remember_episode(
                "mini_procedure",
                f"Tạo mini thủ tục '{name}' cho chủ đề '{topic}'.",
                importance=0.7,
                emotion=0.3,
            )
            self.stats["weak_patch"] += 1
            self._log(f"tạo mini thủ tục: {name}")
        except Exception as e:
            self._log(f"fallback proc err: {e}")

    def _clean(self, text: str) -> str:
        text = str(text or "")
        text = re.sub(r"^```(?:json|python)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text, flags=re.M)
        lines = [ln for ln in text.splitlines() if not re.match(r"^\s*(```|\{|json|python)", ln) or not text]
        return text.strip()
