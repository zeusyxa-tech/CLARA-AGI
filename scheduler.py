"""
CLARA-AGI v1.1 - Scheduled Curriculum.
Tự lên lịch học theo ngày/tuần/tháng:
- study_plan: danh sách chủ đề cần học
- study_log: lịch sử tiến độ học
- spaced_review: ôn kiến thức cũ theo lịch
- daily_quiz: tự kiểm tra 2-3 câu mỗi ngày
- weekly_review: tổng kết cuối tuần
"""
import json, time, random, re, threading
from pathlib import Path
from memory import DB_DIR

DB_PATH = DB_DIR / "clara.db"

STUDY_CMDS = [
    "study plan", "study status", "study on", "study off",
    "study review today", "study weekly"
]


# ---------------- DB helpers ----------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS study_plan(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic TEXT NOT NULL,
  detail TEXT,
  priority REAL DEFAULT 0.5,
  status TEXT DEFAULT 'active',
  assign_date TEXT,
  target_date TEXT,
  progress REAL DEFAULT 0,
  created_at REAL,
  last_reviewed REAL,
  next_review REAL
);
CREATE TABLE IF NOT EXISTS study_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL,
  topic TEXT,
  action TEXT,
  score REAL,
  note TEXT,
  source TEXT DEFAULT 'scheduler'
);
CREATE TABLE IF NOT EXISTS streak(
  id INTEGER PRIMARY KEY CHECK(id = 1),
  streak_days INTEGER DEFAULT 0,
  last_study_date TEXT,
  total_days INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sp_topic ON study_plan(topic);
CREATE INDEX IF NOT EXISTS sl_ts ON study_log(ts);
"""


def _conn():
    import sqlite3
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=5.0)
    c.row_factory = sqlite3.Row
    try:
        c.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    c.executescript(_SCHEMA)
    c.commit()
    return c


def _day_stamp(ts=None):
    if ts is None: ts = time.time()
    return time.strftime("%Y-%m-%d", time.localtime(ts))


# ---------------- Plan ----------------
def add_topic(agi, topic: str, detail: str = "", priority: float = 0.5,
              target_days: int = 7, assign_now: bool = True) -> str:
    c = _conn()
    ts = time.time()
    assign_date = _day_stamp(ts) if assign_now else None
    target_date = _day_stamp(ts + target_days * 86400)
    c.execute(
        "INSERT INTO study_plan(topic,detail,priority,status,assign_date,target_date,created_at,next_review) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (topic.strip(), detail.strip(), priority, "active" if assign_now else "queued",
         assign_date, target_date, ts, ts))
    c.commit()
    c.close()
    if assign_now:
        return f"📚 Đã thêm chủ đề học: {topic} (mục tiêu ~{target_days} ngày)."
    return f"📥 Đã xếp hàng chủ đề: {topic}."


def list_plan(agi, status: str = "active", limit: int = 20) -> str:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM study_plan WHERE status=? ORDER BY priority DESC, created_at DESC LIMIT ?",
        (status, limit)).fetchall()
    c.close()
    if not rows:
        return f"📭 Không có mục '{status}'."
    lines = [f"📋 Kế hoạch [{status}] ({len(rows)}):"]
    for r in rows:
        lines.append(
            f"  • {r['topic']} (p={r['priority']:.2f}) — tiến độ {r['progress']:.0%}, hạn {r['target_date']}")
    return "\n".join(lines)


def mark_progress(agi, topic: str, progress_delta: float = 0.25) -> str:
    c = _conn()
    r = c.execute("SELECT * FROM study_plan WHERE status='active' AND topic LIKE ?",
                  (f"%{topic}%",)).fetchone()
    if not r:
        c.close()
        return f"❌ Không tìm thấy chủ đề đang học: {topic}."
    new_p = min(1.0, max(0.0, r["progress"] + progress_delta))
    status = "done" if new_p >= 1.0 else r["status"]
    c.execute("UPDATE study_plan SET progress=?, status=?, last_reviewed=? WHERE id=?",
              (new_p, status, time.time(), r["id"]))
    c.execute("INSERT INTO study_log(ts,topic,action,score,note) VALUES(?,?,?,?,?)",
              (time.time(), r["topic"], "progress", new_p, f"delta={progress_delta}"))
    c.commit()
    c.close()
    return f"✅ {r['topic']}: cập nhật tiến độ {new_p:.0%}. {'🎉 Hoàn thành!' if status=='done' else ''}"


# ---------------- Spaced review ----------------
def due_reviews(agi, limit: int = 5):
    now = time.time()
    c = _conn()
    rows = c.execute(
        "SELECT * FROM study_plan WHERE status='active' AND next_review<=? ORDER BY next_review ASC LIMIT ?",
        (now, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def apply_spaced_review(agi, row: dict, out: list):
    # ưu tiên dùng semantic memory liên quan để tạo câu hỏi ôn
    sems = agi.mem.recall_semantics(row["topic"], limit=3)
    facts = [s["fact"] for s in sems]
    if not facts:
        facts = [row["detail"]] if row.get("detail") else [row["topic"]]
    q_blob = "\n".join([f"- {f}" for f in facts])
    prompt = (
        f"[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n"
        f"Đây là kiến thức về chủ đề '{row['topic']}':\\n{q_blob}\\n"
        f"Hãy đặt MỘT câu hỏi ôn tập ngắn bằng tiếng Việt (không trả lời, chỉ câu hỏi)."
    )
    question = agi.brain.think("__ANSWER__", prompt, temperature=0.7)
    question = agi._clean(question).strip()
    question = re.sub(r"^(câu hỏi:|hỏi:)", "", question, flags=re.I).strip()
    if len(question) < 5:
        question = f"Tóm tắt lại kiến thức cốt lõi về '{row['topic']}'?"
    ans = agi.chat(question)
    ans_clean = ans.split("\n⏱️")[0].strip()
    ref = agi.brain.think(
        "__REFLECT__",
        f"[USER]{question}[/USER]\n[ANSWER]{ans_clean[:400]}[/ANSWER]",
        temperature=0.2,
    )
    score = agi._extract_score(ref)
    # cập nhật spaced: đơn giản hóa bằng khoảng cách ngày cố định theo score
    if score >= 8:
        days = 3
    elif score >= 5:
        days = 2
    else:
        days = 1
    next_review = time.time() + days * 86400
    c = _conn()
    c.execute("UPDATE study_plan SET next_review=?, last_reviewed=? WHERE id=?",
              (next_review, time.time(), row["id"]))
    c.execute("INSERT INTO study_log(ts,topic,action,score,note) VALUES(?,?,?,?,?)",
              (time.time(), row["topic"], "review", score, f"next_in={days}d"))
    c.commit()
    c.close()
    return {"question": question, "answer": ans_clean, "score": score, "next_in_days": days}


# ---------------- Daily quiz ----------------
def daily_quiz(agi, n: int = 2) -> list:
    # lấy ngẫu nhiên chủ đề đang học/knowledge hiện có
    c = _conn()
    rows = c.execute(
        "SELECT topic FROM study_plan WHERE status='active' ORDER BY random() LIMIT ?",
        (max(1, min(n, 3)),)).fetchall()
    c.close()
    if not rows:
        # fallback: tự hỏi kiến thức hiện có
        rows = [{"topic": "kiến thức hiện có"}]
    results = []
    for r in rows:
        topic = r["topic"]
        sems = agi.mem.recall_semantics(topic, limit=4)
        seed = "\n".join([f"- {s['fact']}" for s in sems]) if sems else topic
        q_prompt = (
            f"Dựa trên kiến thức sau, đặt MỘT câu hỏi kiểm tra ngắn bằng tiếng Việt.\\n{seed}"
        )
        q_raw = agi.brain.think(
            "__ANSWER__",
            "[WORKSPACE][][/WORKSPACE][TOOL_RESULT]không dùng[/TOOL_RESULT]\n" + q_prompt,
            temperature=0.7,
        )
        q = agi._clean(q_raw).strip()
        q = re.sub(r"^(câu hỏi:|hỏi:)", "", q, flags=re.I).strip()
        if not q or len(q) < 4:
            q = f"Về '{topic}', điều quan trọng nhất cần nhớ là gì?"
        ans = agi.chat(q)
        ans_clean = ans.split("\n⏱️")[0].strip()
        crit = agi.brain.think(
            "__REFLECT__",
            f"[USER]{q}[/USER]\n[ANSWER]{ans_clean[:300]}[/ANSWER]",
            temperature=0.2,
        )
        sc = agi._extract_score(crit)
        results.append({"topic": topic, "question": q, "answer": ans_clean, "score": sc})
    return results


# ---------------- Weekly review ----------------
def weekly_review(agi) -> str:
    c = _conn()
    now = time.time()
    week_ago = now - 7 * 86400
    logs = c.execute(
        "SELECT topic, action, score, ts FROM study_log WHERE ts>=? ORDER BY ts ASC",
        (week_ago,)).fetchall()
    sessions = c.execute(
        "SELECT COUNT(DISTINCT date(ts,'localtime')) as days FROM study_log WHERE ts>=?",
        (week_ago,)).fetchone()["days"] or 0
    planned = c.execute(
        "SELECT status, COUNT(*) as n FROM study_plan GROUP BY status").fetchall()
    c.close()
    if not logs:
        return "📭 Chưa có dữ liệu học tập trong tuần này."
    scores = [r["score"] for r in logs if r["score"] is not None]
    avg = (sum(scores) / len(scores)) if scores else 0
    top = {}
    for r in logs:
        top.setdefault(r["topic"], 0)
        top[r["topic"]] += 1
    focus = sorted(top, key=top.get, reverse=True)[:3]
    lines = [
        f"📅 TỔNG KẾT TUẦN — phiên học: {len(logs)} | ngày có học: {sessions}/7 | trung bình: {avg:.1f}/10",
        f"   chủ đề chính: {', '.join(focus or ['(chưa rõ)'])}",
        "Đề xuất tuần sau:",
    ]
    for t in focus:
        lines.append(f"  - Ôn thêm '{t}', 5 phút mỗi ngày.")
    if avg < 6:
        lines.append("  - Giảm số mục learning mới, tăng 30% thời gian review.")
    else:
        lines.append("  - Thêm 1 chủ đề mới trọng bậc cao hơn.")
    return "\n".join(lines)


# ---------------- Streak ----------------
def update_streak(agi) -> dict:
    today = _day_stamp()
    c = _conn()
    r = c.execute("SELECT * FROM streak WHERE id=1").fetchone()
    if not r:
        c.execute("INSERT INTO streak(id,streak_days,last_study_date,total_days) VALUES(?,?,?,?)",
                  (1, 1, today, 1))
        c.commit()
        c.close()
        return {"streak": 1, "total": 1, "today": today}
    streak = r["streak_days"]
    total = r["total_days"] + 1 if r["last_study_date"] != today else r["total_days"]
    if r["last_study_date"] != today:
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        streak = streak + 1 if r["last_study_date"] == yesterday else 1
    c.execute("UPDATE streak SET streak_days=?, last_study_date=?, total_days=? WHERE id=?",
              (streak, today, total, 1))
    c.commit()
    c.close()
    return {"streak": streak, "total": total, "today": today}


# ---------------- Auto integration ----------------
class StudyScheduler:
    def __init__(self, agi, enabled=False, interval=120):
        self.agi = agi
        self.enabled = enabled
        self.interval = interval
        self._running = False
        self._thread = None
        self._prepared_today = False

    def start(self):
        if self._running:
            return False
        self._running = True
        self._thread = _Loop(self)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        return True

    def status(self):
        day = _day_stamp()
        c = _conn()
        rr = c.execute("SELECT COUNT(*) as n FROM study_plan WHERE status='active' AND next_review<=?",
                       (time.time(),)).fetchone()["n"]
        logs = c.execute("SELECT COUNT(*) as n FROM study_log WHERE date(ts,'localtime')=?",
                         (day,)).fetchone()["n"]
        c.close()
        return {"running": self._running, "interval": self.interval,
                "due_reviews": rr, "logs_today": logs}

    def daily_setup(self):
        day = _day_stamp()
        c = _conn()
        n = c.execute("SELECT COUNT(*) as n FROM study_log WHERE date(ts,'localtime')=?", (day,)).fetchone()["n"]
        if n == 0 and not self._prepared_today:
            self._prepared_today = True
            self._assign_daily_topics()
        elif n > 0:
            self._prepared_today = True
        c.close()

    def _assign_daily_topics(self):
        c = _conn()
        queued = c.execute(
            "SELECT * FROM study_plan WHERE status='queued' ORDER BY priority DESC, created_at ASC LIMIT 2"
        ).fetchall()
        due = c.execute(
            "SELECT * FROM study_plan WHERE status='active' AND next_review<=? ORDER BY next_review ASC LIMIT 3",
            (time.time(),)).fetchall()
        c.close()
        topics = []
        for r in due:
            topics.append(f"Ôn tập: {r['topic']}")
        for r in queued:
            topics.append(f"Học mới: {r['topic']}")
        if not topics:
            return
        plan_text = " | ".join(topics[:3])
        self.agi.mem.remember_episode(
            "study_plan",
            f"Kế hoạch hôm nay: {plan_text}",
            importance=0.6,
            emotion=0.2,
        )

    def step(self):
        if not self._running:
            return
        ts = time.localtime(time.time())
        # mỗi giờ đầu tiên của ngày mới thì reset
        if ts.tm_hour == 0 and ts.tm_min < 5 and self._prepared_today:
            self._prepared_today = False
        # review trước nếu có bài đến hạn
        due = due_reviews(self.agi, limit=2)
        for row in due:
            try:
                out = apply_spaced_review(self.agi, row, [])
                update_streak(self.agi)
            except Exception as e:
                pass
        # quiz nhẹ 1-2 câu
        if random.random() < 0.4:
            try:
                qs = daily_quiz(self.agi, n=1)
                for q in qs:
                    c = _conn()
                    c.execute(
                        "INSERT INTO study_log(ts,topic,action,score,note) VALUES(?,?,?,?,?)",
                        (time.time(), q["topic"], "quiz", q["score"], q["question"]),
                    )
                    c.commit()
                    c.close()
                    update_streak(self.agi)
                    if q["score"] >= 7:
                        mark_progress(self.agi, q["topic"], 0.1)
            except Exception:
                pass
        # ngày chủ nhật tuần → weekly review
        if time.localtime().tm_wday == 6 and random.random() < 0.6:
            try:
                report = weekly_review(self.agi)
                self.agi.mem.remember_episode(
                    "weekly_review", report, importance=0.8, emotion=0.1
                )
            except Exception:
                pass
        self.daily_setup()


class _Loop(threading.Thread):
    def __init__(self, sched):
        super().__init__(daemon=True)
        self.sched = sched

    def run(self):
        time.sleep(4)
        while self.sched._running:
            try:
                self.sched.step()
            except Exception as e:
                pass
            for _ in range(int(self.sched.interval)):
                if not self.sched._running:
                    break
                time.sleep(1)


# ---------------- command helpers used by agent/main ----------------
def cmd_study_plan(agi, text: str) -> str:
    t = (text or "").lower().strip()
    if not t or t == "study plan":
        return list_plan(agi, status="active", limit=15)
    if t.startswith("study plan add "):
        topic = t[len("study plan add "):].strip()
        if not topic:
            return "Dùng: study plan add <chủ đề> | study plan add <chủ đề>| <mô tả>."
        detail = ""
        if "|" in topic:
            topic, detail = topic.split("|", 1)
        return add_topic(agi, topic, detail=detail)
    if t.startswith("study plan queued"):
        return list_plan(agi, status="queued", limit=15)
    return (
        "Lệnh:\\n"
        "  study plan                 xem kế hoạch học\\n"
        "  study plan add <chủ đề>    thêm chủ đề mới\\n"
        "  study plan queued          xem chủ đề chờ học\\n"
        "  study status               xem tiến độ/streak/ônn hôm nay"
    )


def cmd_study_status(agi, text: str) -> str:
    c = _conn()
    stats = c.execute(
        "SELECT status, COUNT(*) as n, COALESCE(AVG(progress),0) as avg FROM study_plan GROUP BY status"
    ).fetchall()
    c.close()
    streak = update_streak(agi)
    lines = [
        "📊 Trạng thái học tập:",
        f"  streak: {streak['streak']} ngày | tổng ngày học: {streak['total']}",
        f"  hôm nay: {streak['today']}",
    ]
    for r in stats:
        lines.append(f"  {r['status']}: {r['n']} mục | avg progress={float(r['avg']):.0%}")
    return "\n".join(lines)


def cmd_study_review_today(agi, text: str) -> str:
    rows = due_reviews(agi, limit=5)
    if not rows:
        return "✅ Hôm nay chưa có bài ôn đến hạn. CLARA có thể đi kiểm tra quiz sau."
    out = [f"📝 Ôn tập hôm nay: {len(rows)} mục"]
    for r in rows:
        try:
            res = apply_spaced_review(agi, r, out)
            out.append(
                f"  • {r['topic']}: hỏi={res['question'][:50]} → điểm={res['score']}/10, tái ôn sau {res['next_in_days']} ngày"
            )
        except Exception as e:
            out.append(f"  • {r['topic']}: lỗi={e}")
    return "\n".join(out)


def cmd_study_weekly(agi, text: str) -> str:
    return weekly_review(agi)


def attach_study_commands(agi):
    agi._study_commands = {
        "study plan": cmd_study_plan,
        "study status": cmd_study_status,
        "study review today": cmd_study_review_today,
        "study weekly": cmd_study_weekly,
    }
