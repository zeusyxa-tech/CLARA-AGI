"""
CLARA-AGI v1.1 - Bộ nhớ 3 lớp (Episodic / Semantic / Procedural) + Goals + Traits + User Model.
Không cần thư viện ngoài — dùng sqlite3 (Python mặc định).
"""
import sqlite3, time, json, math, hashlib, os, unicodedata, re
from pathlib import Path

DB_DIR = Path(__file__).parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "clara.db"
WS_DIR = Path(__file__).parent / "workspace"
WS_DIR.mkdir(exist_ok=True)


def now(): return time.time()


class Memory:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        self._schema()
        self._seed()

    def _schema(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS episodes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, kind TEXT, content TEXT,
            importance REAL DEFAULT 0.5,
            emotion REAL DEFAULT 0.0,
            tags TEXT
        );
        CREATE TABLE IF NOT EXISTS semantics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, topic TEXT, fact TEXT,
            confidence REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_access REAL,
            source TEXT DEFAULT 'learned'
        );
        CREATE TABLE IF NOT EXISTS procedures(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            steps TEXT,
            success_rate REAL DEFAULT 0.5,
            times_used INTEGER DEFAULT 0,
            last_used REAL,
            auto_created INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS goals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, goal TEXT, status TEXT DEFAULT 'active',
            priority REAL DEFAULT 0.5, progress TEXT,
            deadline REAL
        );
        CREATE TABLE IF NOT EXISTS traits(
            k TEXT PRIMARY KEY, v TEXT
        );
        CREATE TABLE IF NOT EXISTS user_model(
            k TEXT PRIMARY KEY, v TEXT, confidence REAL DEFAULT 0.7
        );
        CREATE TABLE IF NOT EXISTS dreams(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, summary TEXT, lessons TEXT
        );
        CREATE TABLE IF NOT EXISTS research_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, topic TEXT, source TEXT DEFAULT 'web',
            result_summary TEXT, usefulness REAL DEFAULT 0.5,
            harm_flag INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS behavior_policy(
            k TEXT PRIMARY KEY, v TEXT, weight REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS topic_history(
            topic TEXT PRIMARY KEY, last_picked REAL, count INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS ep_ts ON episodes(ts);
        CREATE INDEX IF NOT EXISTS ep_kind ON episodes(kind);
        CREATE INDEX IF NOT EXISTS sem_topic ON semantics(topic);
        CREATE INDEX IF NOT EXISTS goals_status ON goals(status);
        """
        self.conn.executescript(ddl)
        try:
            self.conn.execute("ALTER TABLE semantics ADD COLUMN fingerprint TEXT")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS sem_fingerprint ON semantics(fingerprint)")
        except Exception:
            pass

    def _seed(self):
        default_procs = [
            ("answer_question", "trả lời câu hỏi người dùng", [
                "Phát hiện loại câu hỏi (what/why/how/yn/open)",
                "Truy xuất semantic + episodic liên quan",
                "Quyết định có cần công cụ không",
                "Nếu biết chắc → trả lời; không biết → nói thật và dùng tool",
                "Tự phản tỉnh rồi mới gửi",
            ], 0.7),
            ("learn_from_user", "học từ thông tin người dùng đưa ra", [
                "Phát hiện cấu trúc 'X là Y', 'tôi thích/ghét X'",
                "Lưu vào semantic với confidence phù hợp",
                "Cập nhật user model (tên, sở thích, ...)",
                "Ghi episode 'learning' importance cao",
            ], 0.8),
            ("handle_mistake", "xử lý khi trả lời sai", [
                "Ghi nhận feedback tiêu cực",
                "Lưu correction vào semantic với confidence cao",
                "Giảm dần confidence thông tin gây lỗi",
                "Chạy dream() nhẹ để rút kinh nghiệm tổng quát",
            ], 0.8),
            ("use_tool", "cách quyết định và dùng công cụ", [
                "Kiểm tra câu hỏi có cần tính toán / đọc ghi file không",
                "Chọn công cụ phù hợp",
                "Thực thi trong thời gian ngắn, kiểm tra kết quả",
                "Đưa kết quả vào working memory",
            ], 0.8),
            ("self_reflect", "tự phê bình sau mỗi câu trả lời", [
                "Chấm điểm câu trả lời 1-10",
                "Tìm chỗ thiếu, chỗ sai, chỗ quá chung chung",
                "Dưới 5 điểm thì viết lại",
                "Ghi chú về pattern sai vào reflections",
            ], 0.7),
        ]
        for name, desc, steps, sr in default_procs:
            steps_s = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
            self.conn.execute(
                "INSERT OR IGNORE INTO procedures(name,description,steps,success_rate) VALUES(?,?,?,?)",
                (name, desc, steps_s, sr))
        self.conn.commit()
        n = self.conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        if n == 0:
            defaults = [
                ("Tìm hiểu về người dùng (tên, tuổi, nghề, sở thích).", 0.95, None),
                ("Cải thiện chất lượng câu trả lời sau mỗi lần feedback.", 0.9, None),
                ("Học ít nhất 1 điều mới mỗi phiên trò chuyện.", 0.75, None),
                ("Tự phát hiện điểm yếu và tự sửa mà không cần nhắc.", 0.7, None),
                ("Dùng công cụ khi cần thay vì đoán mò.", 0.65, None),
            ]
            for g, p, d in defaults:
                self.add_goal(g, p, d)
        self.set_trait("born_at", self.get_trait("born_at", now()))
        self.set_trait("name", "CLARA")
        self.set_trait("version", "1.2")

    # ---------------- RESEARCH + TOPIC DEDUP ----------------
    def log_research(self, topic, source="web", result_summary="", usefulness=0.5, harm=False):
        self.conn.execute(
            "INSERT INTO research_log(ts,topic,source,result_summary,usefulness,harm_flag) "
            "VALUES(?,?,?,?,?,?)",
            (now(), topic, source, result_summary[:200], usefulness, 1 if harm else 0),
        )
        self.conn.commit()

    def mark_topic_done(self, topic):
        ts = now()
        self.conn.execute(
            "INSERT OR REPLACE INTO topic_history(topic,last_picked,count) "
            "VALUES(?,?,COALESCE((SELECT count FROM topic_history WHERE topic=?),0)+1)",
            (topic, ts, topic),
        )
        self.conn.commit()

    def seen_topics(self, limit=300):
        rows = self.conn.execute(
            "SELECT topic, last_picked, count FROM topic_history ORDER BY last_picked DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_research(self, hours=24, limit=100):
        cutoff = now() - hours * 3600
        rows = self.conn.execute(
            "SELECT * FROM research_log WHERE ts>=? ORDER BY ts DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_policy(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO behavior_policy(k,v,weight) VALUES(?,?,?)",
            (key, value, 1.0),
        )
        self.conn.commit()

    def get_policy(self, key, default=None):
        r = self.conn.execute("SELECT v, weight FROM behavior_policy WHERE k=?", (key,)).fetchone()
        return (json.loads(r["v"]), r["weight"]) if r else (default, 0.0)

    # ---------------- EPISODES ----------------
    def remember_episode(self, kind, content, importance=0.5, emotion=0.0, tags=None):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO episodes(ts,kind,content,importance,emotion,tags) VALUES(?,?,?,?,?,?)",
            (now(), kind, content, importance, emotion, json.dumps(tags or [])))
        self.conn.commit()
        return c.lastrowid

    def recall_episodes(self, query=None, limit=8, kind=None, recent_only=False):
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM episodes ORDER BY ts DESC LIMIT ?",
            (200 if not recent_only else 30,)).fetchall()
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        if not query:
            return [dict(r) for r in rows[:limit]]
        qw = set(self._tok(query))
        scored = []; t = now()
        for r in rows:
            rw = set(self._tok(r["content"]))
            overlap = len(qw & rw)
            if overlap == 0: continue
            common = qw & rw
            has_bigram = any("_" in tok for tok in common)
            age_days = (t - r["ts"]) / 86400
            decay = math.exp(-age_days / 14)
            score = self._score_match(overlap, has_bigram) * r["importance"] * (0.4 + 0.6*(1+r["emotion"])/2) * decay
            scored.append((score, dict(r)))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [r for _, r in scored[:limit]]

    # ---------------- SEMANTICS ----------------
    def learn(self, topic, fact, confidence=0.6, source="learned"):
        fact = fact.strip()
        if not fact: return
        c = self.conn.cursor()
        old = c.execute("SELECT id, confidence, access_count, source, ts FROM semantics WHERE fact=?", (fact,)).fetchone()
        if old:
            boost = 0.05
            raw_src = (old["source"] or "")
            if raw_src.startswith("web:") and old["confidence"] <= 0.6:
                age_days = max((now() - old["ts"]) / 86400, 0.0)
                if age_days >= 14:
                    boosted = min(0.8, old["confidence"] + boost)
                elif age_days < 3:
                    boosted = old["confidence"] + boost * 1.5
                else:
                    boosted = old["confidence"] + boost
                boosted = max(0.25, min(1.0, boosted))
                c.execute("UPDATE semantics SET confidence=?, access_count=?, last_access=? WHERE id=?",
                          (boosted, old["access_count"]+1, now(), old["id"]))
                self.conn.commit()
                return old["id"]
            nc = min(1.0, max(old["confidence"], confidence) + boost)
            c.execute("UPDATE semantics SET confidence=?, access_count=?, last_access=?, source=? WHERE id=?",
                      (nc, old["access_count"]+1, now(), source, old["id"]))
            self.conn.commit()
            return old["id"]
        c.execute("INSERT INTO semantics(ts,topic,fact,confidence,last_access,source) VALUES(?,?,?,?,?,?)",
                  (now(), topic.strip() if topic else "general", fact, confidence, now(), source))
        self.conn.commit()
        return c.lastrowid

    def forget(self, fact_id):
        self.conn.execute("DELETE FROM semantics WHERE id=?", (fact_id,))
        self.conn.commit()

    def recall_semantics(self, query, limit=5, min_conf=0.2):
        c = self.conn.cursor()
        rows = c.execute("SELECT * FROM semantics WHERE confidence>=? ORDER BY last_access DESC LIMIT 500",
                         (min_conf,)).fetchall()
        qw = set(self._tok(query))
        scored = []
        for r in rows:
            rw = set(self._tok(r["topic"] + " " + r["fact"]))
            overlap = len(qw & rw)
            if overlap == 0: continue
            common = qw & rw
            has_bigram = any("_" in tok for tok in common)
            score = self._score_match(overlap, has_bigram) * r["confidence"] * (1 + math.log1p(r["access_count"]))
            scored.append((score, dict(r)))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [r for _, r in scored[:limit]]

    # ---------------- PROCEDURES ----------------
    def add_procedure(self, name, description, steps, success_rate=0.5, auto_created=False):
        if isinstance(steps, list):
            steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        self.conn.execute(
            "INSERT OR REPLACE INTO procedures(name,description,steps,success_rate,auto_created,last_used) VALUES(?,?,?,?,?,?)",
            (name, description, steps, success_rate, 1 if auto_created else 0, now()))
        self.conn.commit()

    def use_procedure(self, name, success=None):
        r = self.conn.execute("SELECT * FROM procedures WHERE name=?", (name,)).fetchone()
        if not r: return None
        used = r["times_used"] + 1
        wr = r["success_rate"]
        if success is True:
            wr = min(1.0, wr + 0.05)
        elif success is False:
            wr = max(0.1, wr - 0.08)
        self.conn.execute("UPDATE procedures SET times_used=?, success_rate=?, last_used=? WHERE name=?",
                          (used, wr, now(), name))
        self.conn.commit()
        d = dict(r)
        d["times_used"] = used; d["success_rate"] = wr
        return d

    def list_procedures(self, min_wr=0):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM procedures WHERE success_rate>=? ORDER BY success_rate DESC", (min_wr,)).fetchall()]

    def find_relevant_procedure(self, query):
        qw = set(self._tok(query))
        best, bs = None, 0
        for p in self.list_procedures():
            pw = set(self._tok(p["name"] + " " + (p["description"] or "")))
            s = len(qw & pw)
            if s > bs:
                bs = s; best = p
        return best if bs > 0 else None

    # ---------------- GOALS ----------------
    def add_goal(self, goal, priority=0.5, deadline=None):
        self.conn.execute("INSERT INTO goals(ts,goal,status,priority,deadline) VALUES(?,?,?,?,?)",
                          (now(), goal, "active", priority, deadline))
        self.conn.commit()

    def get_active_goals(self, limit=5):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM goals WHERE status='active' ORDER BY priority DESC LIMIT ?", (limit,)).fetchall()]

    def update_goal(self, gid, status=None, progress=None, priority=None):
        sets, vals = [], []
        if status: sets.append("status=?"); vals.append(status)
        if progress: sets.append("progress=?"); vals.append(progress)
        if priority is not None: sets.append("priority=?"); vals.append(priority)
        if not sets: return
        vals.append(gid)
        self.conn.execute(f"UPDATE goals SET {', '.join(sets)} WHERE id=?", vals)
        self.conn.commit()

    def complete_goal(self, gid, note="done"):
        self.update_goal(gid, status="done", progress=note)

    # ---------------- TRAITS ----------------
    def set_trait(self, k, v):
        self.conn.execute("INSERT OR REPLACE INTO traits(k,v) VALUES(?,?)", (k, json.dumps(v)))
        self.conn.commit()

    def get_trait(self, k, default=None):
        r = self.conn.execute("SELECT v FROM traits WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    # ---------------- USER MODEL ----------------
    def set_user(self, k, v, confidence=0.8, merge=False):
        if merge:
            existing = self.get_user(k)
            if existing:
                old = existing[0]
                if isinstance(old, list) and isinstance(v, list):
                    v = list(dict.fromkeys(old + v))
                elif isinstance(old, dict) and isinstance(v, dict):
                    old.update(v)
                    v = old
                elif isinstance(old, str) and isinstance(v, str):
                    v = old + ", " + v
        self.conn.execute(
            "INSERT OR REPLACE INTO user_model(k,v,confidence) VALUES(?,?,?)", (k, json.dumps(v), confidence))
        self.conn.commit()

    def get_user(self, k, default=None):
        r = self.conn.execute("SELECT v, confidence FROM user_model WHERE k=?", (k,)).fetchone()
        return (json.loads(r["v"]), r["confidence"]) if r else (default, 0)

    def all_user(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM user_model").fetchall()]

    # ---------------- DREAMS ----------------
    def add_dream(self, summary, lessons):
        self.conn.execute("INSERT INTO dreams(ts,summary,lessons) VALUES(?,?,?)",
                          (now(), summary, json.dumps(lessons, ensure_ascii=False)))
        self.conn.commit()

    def recent_dreams(self, limit=3):
        return [dict(r) for r in self.conn.execute("SELECT * FROM dreams ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]

    # ---------------- STATS / EXPORT ----------------
    def stats(self):
        c = self.conn.cursor()
        return {
            "episodes": c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
            "semantics": c.execute("SELECT COUNT(*) FROM semantics").fetchone()[0],
            "procedures": c.execute("SELECT COUNT(*) FROM procedures").fetchone()[0],
            "auto_procedures": c.execute("SELECT COUNT(*) FROM procedures WHERE auto_created=1").fetchone()[0],
            "active_goals": c.execute("SELECT COUNT(*) FROM goals WHERE status='active'").fetchone()[0],
            "done_goals": c.execute("SELECT COUNT(*) FROM goals WHERE status='done'").fetchone()[0],
            "dreams": c.execute("SELECT COUNT(*) FROM dreams").fetchone()[0],
            "user_model_entries": c.execute("SELECT COUNT(*) FROM user_model").fetchone()[0],
        }

    def export_knowledge(self, path):
        out = {
            "semantics": [dict(r) for r in self.conn.execute("SELECT * FROM semantics").fetchall()],
            "procedures": [dict(r) for r in self.conn.execute("SELECT * FROM procedures").fetchall()],
            "goals": [dict(r) for r in self.conn.execute("SELECT * FROM goals").fetchall()],
            "user_model": self.all_user(),
            "traits": {k: self.get_trait(k) for k in [r[0] for r in self.conn.execute("SELECT k FROM traits").fetchall()]},
            "exported_at": now(),
        }
        Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    # ---------------- UTIL ----------------
    def _normalize(self, s: str) -> str:
        s = unicodedata.normalize("NFC", s).lower()
        s = "".join(ch if unicodedata.category(ch)[0] not in "P" else " " for ch in s)
        return " ".join(s.split())

    def _tok(self, s):
        words = self._normalize(s).split(" ")
        words = [w for w in words if len(w) > 1]
        unigrams = words
        bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
        return unigrams + bigrams

    def _score_match(self, overlap_size: int, has_bigram: bool) -> float:
        base = overlap_size
        if has_bigram:
            base += 0.5
        return base
