"""
CLARA-AGI v1.1 - Auto-Learn / Idle Self-Improvement Loop.
Chạy nền khi không có người dùng nói chuyện: tự củng cố kiến thức, phản tỉnh,
tự đặt câu hỏi, phát hiện lỗ hổng kiến thức, tạo mục tiêu mới.
"""
import time, json, random, re, threading
from brain import T_DREAM, T_ANSWER, T_REFLECT, T_PLAN, T_SKILL


class AutoLearner:
    """Một thread nền, mỗi `interval` giây tự chạy 1 hoạt động học tập."""

    def __init__(self, agi, interval=25, max_steps=None, verbose=True):
        self.agi = agi
        self.interval = interval
        self.max_steps = max_steps
        self.verbose = verbose
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self.steps_done = 0
        self.stats = {"dream":0, "self_qa":0, "reflect":0, "new_goals":0,
                      "new_skills":0, "consolidate":0}

    # ---------- điều khiển ----------
    def start(self):
        if self._running: return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        return True

    def status(self):
        return {"running": self._running, "interval": self.interval,
                "steps_done": self.steps_done, "stats": self.stats}

    # ---------- vòng lặp chính ----------
    def _loop(self):
        # đợi một chút sau khi khởi động trước khi tự học
        time.sleep(5)
        while self._running:
            if self.max_steps and self.steps_done >= self.max_steps:
                self._log(f"Đã đạt {self.max_steps} bước tự học, dừng.")
                self._running = False; break
            try:
                self._one_idle_step()
            except Exception as e:
                self._log(f"lỗi tự học: {e}")
            # đợi, nhưng kiểm tra cờ mỗi giây để stop mượt
            for _ in range(int(self.interval)):
                if not self._running: break
                time.sleep(1)

    def _log(self, msg):
        if self.verbose:
            t = time.strftime("%H:%M:%S")
            print(f"\r💤 [{t}] tự học: {msg}")

    # ---------- một bước tự học ----------
    def _one_idle_step(self):
        self.steps_done += 1
        activities = [
            ("consolidate", 0.25),
            ("reflect_old", 0.20),
            ("self_qa",    0.20),
            ("dream",      0.15),
            ("goal_check", 0.10),
            ("curiosity",  0.10),
        ]
        name = self._weighted_choice(activities)
        with self._lock:
            getattr(self, f"_act_{name}")()

    def _weighted_choice(self, items):
        names, weights = zip(*items)
        total = sum(weights)
        r = random.random() * total
        acc = 0
        for n, w in items:
            acc += w
            if r <= acc: return n
        return names[0]

    # ---------- các hoạt động ----------
    def _act_consolidate(self):
        """Củng cố kiến thức: tìm các fact cũ ít dùng, nếu đúng thì tăng confidence."""
        sem = self.agi.mem.recall_semantics("", limit=50)
        # chọn ngẫu nhiên 1-3 fact cũ
        random.shuffle(sem)
        picked = [s for s in sem if s["confidence"] < 0.95][:3]
        if not picked:
            return
        facts_blob = "\n".join(f"- {s['fact']} (conf={s['confidence']:.2f})" for s in picked)
        prompt = (f"[WORKSPACE][{{\"role\":\"system\",\"content\":\"consolidation\"}}][/WORKSPACE]\n"
                  f"[TOOL_RESULT]không dùng[/TOOL_RESULT]\n"
                  f"Đây là những kiến thức tôi đã học:\n{facts_blob}\n"
                  f"Hãy tìm những mâu thuẫn hoặc trùng lặp. Nếu tất cả nhất quán, chỉ trả về 'OK'. "
                  f"Nếu có mâu thuẫn, chỉ ra cái nào đáng giữ.")
        out = self.agi.brain.think(T_ANSWER, prompt, temperature=0.3)
        out_clean = self.agi._clean(out)
        self.agi.mem.remember_episode("consolidation",
            f"Củng cố {len(picked)} facts. Nhận xét: {out_clean[:200]}",
            importance=0.4, emotion=0.0)
        self.stats["consolidate"] += 1
        self._log(f"củng cố {len(picked)} kiến thức")

    def _act_reflect_old(self):
        """Phản tỉnh về một câu trả lời cũ có feedback tệ."""
        eps = self.agi.mem.recall_episodes(kind="mistake", limit=10)
        if not eps: return
        e = random.choice(eps)
        prompt = f"[ANSWER]{e['content'][:300]}[/ANSWER]"
        critique = self.agi.brain.think(T_REFLECT, f"[USER] (cũ)[/USER]\n{prompt}", temperature=0.3)
        score = self.agi._extract_score(critique)
        if score < 6:
            # tự tạo skill nếu cần
            self.agi._maybe_create_skill("mistake from past", e["content"][:200], critique)
            self.stats["new_skills"] += 1
        self.stats["reflect"] += 1
        self._log(f"phản tỉnh ký ức cũ (điểm {score}/10)")

    def _act_self_qa(self):
        """Tự đặt câu hỏi về chính kiến thức mình có, rồi tự trả lời."""
        sem = self.agi.mem.recall_semantics("", limit=30)
        if len(sem) < 2: return
        facts = "\n".join(f"- {s['fact']}" for s in random.sample(sem, min(5, len(sem))))
        q_prompt = (f"Dựa trên các kiến thức sau, hãy đặt MỘT câu hỏi suy luận thú vị bằng tiếng Việt "
                    f"(không trả lời, chỉ đặt câu hỏi):\n{facts}")
        question = self.agi.brain.think(T_ANSWER, "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + q_prompt, temperature=0.7)
        question = self.agi._clean(question)
        question = re.sub(r"^(câu hỏi:|hỏi:)", "", question, flags=re.I).strip()
        if not question or len(question) < 8: return
        # tự trả lời (giả lập user input)
        ans = self.agi.chat(question)
        ans_clean = ans.split("\n⏱️")[0]
        # tự chấm
        ref_prompt = f"[USER]{question}[/USER]\n[ANSWER]{ans_clean[:400]}[/ANSWER]"
        ref = self.agi.brain.think(T_REFLECT, ref_prompt, temperature=0.2)
        score = self.agi._extract_score(ref)
        if score < 5:
            self.agi.mem.remember_episode("self_qa_mistake",
                f"Tự hỏi: {question}\nTự trả lời: {ans_clean[:200]}\nPhê bình: {ref[:200]}",
                importance=0.6, emotion=-0.2)
        else:
            self.agi.mem.learn("inferred", ans_clean[:200], confidence=0.4, source="self_qa")
        self.stats["self_qa"] += 1
        self._log(f"tự hỏi: {question[:60]}... → {score}/10")

    def _act_dream(self):
        """Ngủ mơ: tổng hợp ký ức gần đây thành bài học."""
        d = self.agi.dream()
        n = len(d.get("lessons", []))
        self.stats["dream"] += 1
        self._log(f"ngủ mơ, rút {n} bài học")

    def _act_goal_check(self):
        """Xem lại mục tiêu, đề xuất thêm hoặc hoàn thành."""
        goals = self.agi.mem.get_active_goals(10)
        if not goals: return
        g = random.choice(goals)
        # đánh giá tiến độ
        sems = self.agi.mem.recall_semantics(g["goal"], limit=5)
        progress = f"Đã có {len(sems)} facts liên quan."
        self.agi.mem.update_goal(g["id"], progress=progress)
        # nếu đã có nhiều evidence, đánh dấu done
        if len(sems) >= 5 and "tìm hiểu" in g["goal"].lower():
            self.agi.mem.complete_goal(g["id"], progress="auto-done qua tự học")
            self.stats["new_goals"] += 1
            self._log(f"hoàn thành mục tiêu: {g['goal'][:50]}")
            # tạo mục tiêu mới
            new_prompt = (f"Các mục tiêu cũ: {json.dumps([gg['goal'] for gg in goals], ensure_ascii=False)}\n"
                          f"Hãy đề xuất MỘT mục tiêu mới ngắn gọn, cụ thể cho tôi (1 câu tiếng Việt).")
            new_goal = self.agi.brain.think(T_ANSWER,
                "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + new_prompt, temperature=0.7)
            new_goal = self.agi._clean(new_goal)
            if len(new_goal) > 10 and len(new_goal) < 200:
                self.agi.mem.add_goal(new_goal, priority=0.5)
                self.stats["new_goals"] += 1
                self._log(f"thêm mục tiêu mới: {new_goal[:50]}")
        else:
            self._log(f"xem mục tiêu: {g['goal'][:50]}... ({progress})")

    def _act_curiosity(self):
        """Suy nghĩ về những điều chưa biết, tạo câu hỏi để chờ hỏi người dùng."""
        um = self.agi.mem.all_user()
        known = [u["k"] for u in um]
        known_str = ", ".join(known) if known else "(chưa biết gì)"
        prompt = (f"Tôi đang biết về người dùng: {known_str}.\n"
                  f"Hãy đề xuất MỘT câu hỏi tự nhiên, lịch sự để tìm hiểu thêm về người dùng "
                  f"(chỉ đưa câu hỏi, không giải thích):")
        q = self.agi.brain.think(T_ANSWER,
            "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + prompt, temperature=0.7)
        q = self.agi._clean(q)
        q = re.sub(r"^(câu hỏi:|hỏi:)", "", q, flags=re.I).strip()
        if len(q) > 10 and len(q) < 200 and "?" in q:
            self.agi.mem.remember_episode("pending_question", q, importance=0.5, emotion=0.2)
            self._log(f"chuẩn bị hỏi bạn: {q[:60]}")
        else:
            self._log("tư duy vẩn vơ...")
