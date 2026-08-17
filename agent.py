"""
CLARA-AGI v1.4 - Global Workspace Agent (9-step cognitive cycle).
"""
import re, json, time, math, random
from pathlib import Path
from memory import Memory
from brain import Brain, T_ANSWER, T_PLAN, T_TOOL, T_REFLECT, T_REWRITE, T_SKILL, T_DREAM
from tools import parse_and_dispatch

try:
    from scheduler import attach_study_commands, StudyScheduler
    _HAS_SCHEDULER = True
except Exception:
    _HAS_SCHEDULER = False
try:
    from self_patcher import propose_patch, smoke_test, rollback, list_backups
    _HAS_SELF_PATCHER = True
except Exception:
    _HAS_SELF_PATCHER = False


class ClarasAGI:
    def __init__(self, force_micro=False, model=None, dream_every=10, auto_skill=True,
                 profile="mobile_12gb_safe", idle_study=False, allow_network=False,
                 language=None):
        self.mem = Memory()
        self.brain = Brain(force_micro=force_micro, model=model, language=language or "vi")
        self.wm = []
        self.dream_every = dream_every
        self.auto_skill = auto_skill
        self.language = self.brain.language
        self.turn_count = self.mem.get_trait("turn_count", 0) or 0
        self.traits = {
            "name": self.mem.get_trait("name", "CLARA"),
            "version": self.mem.get_trait("version", "1.4"),
            "born_at": float(self.mem.get_trait("born_at", time.time()) or time.time()),
            "curiosity": self.mem.get_trait("curiosity", 0.7),
            "honesty": self.mem.get_trait("honesty", 0.9),
            "empathy": self.mem.get_trait("empathy", 0.6),
            "verbosity": self.mem.get_trait("verbosity", 0.5),
        }
        self.first_run = self.mem.stats()["episodes"] == 0
        self._study = None
        self._command_registry = {}
        self._init_command_registry()
        self.history = []
        self.profile_name = profile
        self.idle_study = idle_study
        self.allow_network = allow_network
        if _HAS_SCHEDULER:
            attach_study_commands(self)
            self._study = StudyScheduler(self, enabled=False, interval=120)
            try:
                if getattr(self, "idle_study", False):
                    self._study.start()
            except Exception:
                pass

    # ------------------ CORE CYCLE ------------------
    def chat(self, user_text: str) -> str:
        start = time.time()
        self.turn_count += 1
        self.mem.set_trait("turn_count", self.turn_count)
        text = user_text.strip()
        if not text:
            return "Bạn chưa nói gì 😊"

        special = self._handle_special_commands(text)
        if special is not None:
            return special

        self.wm = [{"role": "user", "content": text}]

        # 1. PERCEIVE
        emotion = self._detect_emotion(text)
        self.wm.append({"role": "emotion", "content": emotion})

        # Theory of Mind: nhìn nhận người dùng đang cần gì
        tom = self._theory_of_mind(text)
        self.wm.append({"role": "tom", "content": tom})

        # 2. RETRIEVE
        sem = self.mem.recall_semantics(text, limit=5)
        epi = self.mem.recall_episodes(text, limit=5)
        procs = self.mem.find_relevant_procedure(text)
        goals = self.mem.get_active_goals(4)
        if sem:
            self.wm.append({"role": "semantic_hits", "content": [s["fact"] for s in sem]})
        if epi:
            self.wm.append({"role": "episodic_hits", "content": [e["content"][:120] for e in epi]})
        if procs:
            self.wm.append({"role": "procedure", "content": {"name": procs["name"], "steps": procs["steps"][:200]}})
        if goals:
            self.wm.append({"role": "active_goals", "content": [g["goal"][:80] for g in goals]})

        # User model
        um = self.mem.all_user()
        if um:
            um_dict = {}
            for u in um[:6]:
                try:
                    um_dict[u["k"]] = json.loads(u["v"])
                except Exception:
                    um_dict[u["k"]] = u["v"]
            self.wm.append({"role": "user_model", "content": um_dict})

        # Chat history
        if self.history:
            self.wm.append({"role": "chat_history", "content": self.history[-6:]})

        # 3. FEEL
        uncertainty = self._uncertainty(text, sem, epi)
        curiosity_bonus = self.traits["curiosity"] * 0.15
        uncertainty = min(1.0, uncertainty + curiosity_bonus - (0.1 if procs else 0))
        self.wm.append({"role": "uncertainty", "content": uncertainty})

        # 4. PLAN
        plan_prompt = f"Người dùng nói: {text}\n[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]"
        plan_raw = self.brain.think(T_PLAN, plan_prompt, temperature=0.3)
        plan = self._parse_plan(plan_raw)
        self.wm.append({"role": "plan", "content": plan})

        # 5-6. TOOL + ACT
        tool_result = ""
        tool_used = "none"
        tool_args = plan.get("tool_args") or ""
        if plan.get("needs_tool") and tool_args and tool_args != "none":
            try:
                tool_result = parse_and_dispatch(self, tool_args)
                tool_used = plan.get("tool_name", tool_args.split()[0])
                self.mem.use_procedure("use_tool", success=("❌" not in tool_result and "Lỗi" not in tool_result))
            except Exception as e:
                tool_result = f"❌ Lỗi khi dùng tool: {e}"
            self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})

        if tool_used == "none":
            forced = self._forced_tool(text)
            if forced:
                try:
                    tool_result = parse_and_dispatch(self, forced)
                    tool_used = forced.split()[0]
                    self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
                except Exception as e:
                    tool_result = f"❌ {e}"

        if tool_used == "none":
            retry_prompt = (
                f"Người dùng yêu cầu dùng tool: {text}\n"
                f"[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]\n"
                "Chỉ trả về MỘT dòng: '<tool_name> <args>' hoặc 'none'. Bắt đầu bằng: calc/read/write/list/run_python/search/now."
            )
            retry_raw = self.brain.think("__TOOL__", retry_prompt, temperature=0.1, num_predict=120)
            m = re.search(r"^(calc|read|write|list|run_python|search|now|help|none)\s+(.*)", retry_raw.strip(), re.S | re.I)
            if m:
                try:
                    tool_result = parse_and_dispatch(self, m.group(0).strip())
                    tool_used = m.group(1).lower()
                    self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
                except Exception as e:
                    tool_result = f"❌ {e}"

        for _ in range(2):
            if tool_used == "none":
                break
            next_prompt = (
                f"Người dùng: {text}\n"
                f"[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]\n"
                f"[TOOL_RESULT]{tool_result or 'không dùng'}[/TOOL_RESULT]\n"
                "Nếu kết quả công cụ trên chưa đủ để trả lời, hãy chọn công cụ tiếp theo cần thiết. "
                "Chỉ trả về MỘT dòng: '<tool_name> <args>' hoặc 'none'."
            )
            next_raw = self.brain.think("__TOOL__", next_prompt, temperature=0.1, num_predict=120)
            m = re.search(r"^(calc|read|write|list|run_python|search|now|help|none)\s+(.*)", next_raw.strip(), re.S | re.I)
            if not m:
                break
            next_tool = m.group(1).lower()
            next_args = m.group(2).strip()
            if next_tool == "none":
                break
            try:
                tool_result = parse_and_dispatch(self, f"{next_tool} {next_args}")
                tool_used = next_tool
                self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
            except Exception as e:
                tool_result = f"❌ {e}"
                tool_used = "none"
                break

        # 7. ANSWER
        ans_prompt = (
            f"[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False, indent=2)}[/WORKSPACE]\n"
            f"[TOOL_RESULT]{tool_result or 'không dùng'}[/TOOL_RESULT]\n"
            f"Người dùng: {text}\n"
            "Hãy trả lời tiếng Việt ngắn gọn, tự nhiên, 2-5 câu."
        )
        answer = self.brain.think(T_ANSWER, ans_prompt, temperature=0.5)
        answer = self._clean(answer)

        # 8. REFLECT
        ref_prompt = (
            f"[USER]{text}[/USER]\n"
            f"[ANSWER]{answer}[/ANSWER]\n"
            f"[WM]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WM]\n"
        )
        reflection = self.brain.think(T_REFLECT, ref_prompt, temperature=0.2)
        score = self._extract_score(reflection)
        rewritten = False
        if score < 6:
            rw_prompt = (
                f"[ORIGINAL]{answer}[/ORIGINAL]\n"
                f"[CRITIQUE]{reflection}[/CRITIQUE]\n"
                f"[USER]{text}[/USER]\n"
                f"[TOOL_RESULT]{tool_result or 'không dùng'}[/TOOL_RESULT]\n"
                "Viết lại câu trả lời tốt hơn (tiếng Việt, 2-4 câu)."
            )
            answer2 = self.brain.think(T_REWRITE, rw_prompt, temperature=0.3)
            answer2 = self._clean(answer2)
            if len(answer2) > 15 and answer2 != answer:
                answer = answer2
                rewritten = True

        # 9. CONSOLIDATE
        importance = min(1.0, 0.25 + abs(emotion)*0.4 + uncertainty*0.25 + (0.1 if tool_used != "none" else 0))
        self.mem.remember_episode("conversation", f"User: {text}\nCLARA: {answer}",
                                   importance=importance, emotion=emotion, tags=self._tags(text))
        self._auto_learn(text, answer)
        self._update_user_model(text, answer, emotion)
        self._progress_goals(text, answer)

        self.mem.use_procedure("answer_question", success=(score >= 6))

        if self.auto_skill and score < 4 and text:
            self._maybe_create_skill(text, answer, reflection)

        dream_note = ""
        if self.dream_every and self.turn_count % self.dream_every == 0:
            dr = self.dream()
            dream_note = f"\n💤 Tôi vừa 'ngủ mơ' và rút ra {len(dr.get('lessons', []))} bài học."
        self.history.append({"user": text[:200], "assistant": answer[:200]})
        if len(self.history) > 8:
            self.history = self.history[-8:]

        elapsed = (time.time() - start) * 1000
        status = self.brain.status()["backend"]
        sure = int((1 - uncertainty) * 100)
        foot = f"\n\n⏱️ {elapsed:.0f}ms · 🧠 {status} · chấc {sure}%"
        if rewritten:
            foot += " · 💭 tự sửa sau phản tỉnh"
        if dream_note:
            foot += dream_note
        return answer + foot

    # ------------------ COMMAND REGISTRY ------------------
    def _register_command(self, name, fn):
        self._command_registry[name] = fn

    def _init_command_registry(self):
        self._register_command("quit", lambda agi, text: None)
        self._register_command("exit", lambda agi, text: None)
        self._register_command("thoát", lambda agi, text: None)
        self._register_command("bye", lambda agi, text: None)
        self._register_command("bye bye", lambda agi, text: None)
        self._register_command("help", lambda agi, text: agi._help_text())
        self._register_command("trợ giúp", lambda agi, text: agi._help_text())
        self._register_command("?", lambda agi, text: agi._help_text())
        self._register_command("status", lambda agi, text: agi._status_text())
        self._register_command("trạng thái", lambda agi, text: agi._status_text())
        self._register_command("dream", lambda agi, text: json.dumps(agi.dream(), ensure_ascii=False, indent=2))
        self._register_command("export", lambda agi, text: agi._export_knowledge())
        self._register_command("commands", lambda agi, text: agi._commands_text())
        self._register_command("goal", lambda agi, text: agi._add_goal_from_text(text))
        self._register_command("forget", lambda agi, text: agi._forget_from_text(text))
        self._register_command("compliance", lambda agi, text: agi._compliance_check(text))
        self._register_command("check", lambda agi, text: agi._quick_check(text))
        self._register_command("income_roadmap", lambda agi, text: agi._income_roadmap(text[len("income_roadmap"):].strip()))
        self._register_command("income_focus", lambda agi, text: agi._income_focus(text[len("income_focus"):].strip()))
        self._register_command("income_opportunity_finder", lambda agi, text: agi._income_opportunity_finder(text[len("income_opportunity_finder"):].strip()))
        self._register_command("opportunity", lambda agi, text: agi._income_opportunity_finder(text[len("opportunity"):].strip()))
        self._register_command("income_portfolio", lambda agi, text: agi._income_portfolio(text[len("income_portfolio"):].strip()))
        self._register_command("review candidates", lambda agi, text: agi._review_candidates())
        self._register_command("approve memory", lambda agi, text: agi._approve_memory(text))
        self._register_command("reject memory", lambda agi, text: agi._reject_memory(text))
        self._register_command("góp ý ngôn ngữ", lambda agi, text: agi._language_feedback(text))
        self._register_command("idle-study", lambda agi, text: agi._run_idle_study())
        self._register_command("growth status", lambda agi, text: agi._growth_status())
        self._register_command("growth report", lambda agi, text: agi._growth_report())

    def _handle_special_commands(self, text):
        low = text.lower().strip()
        for key, fn in self._command_registry.items():
            if low == key or low.startswith(key + " ") or low.startswith(key + ":"):
                return fn(self, text)
        return None

    # ------------------ FEEDBACK ------------------
    def feedback(self, text):
        low = text.lower()
        rating = 0
        if any(w in low for w in ["tốt","hay","đúng","cảm ơn","tuyệt","great","good","love","thích"]):
            rating = 1
        elif any(w in low for w in ["tệ","sai","dốt","chán","bad","không đúng","kém","ghét","bực"]):
            rating = -1
        correction = re.sub(r"^(tốt|tệ|sai|hay|good|bad|ok|đúng|cảm ơn|tuyệt|kém)[\s:,.\\-]*",
                            "", low, count=1).strip()
        if rating == 0 and not correction:
            return "Hãy nói rõ 'tốt' hoặc 'tệ vì <sửa lại>' để tôi học nhé."
        if correction:
            self.mem.learn("correction", correction, confidence=0.85, source="user_feedback")
            self.mem.remember_episode("correction", correction, importance=0.8, emotion=-0.4 if rating<0 else 0.2)
        last = self.mem.recall_episodes(kind="conversation", limit=1, recent_only=True)
        if last and rating < 0:
            self.mem.remember_episode("mistake", f"Sai: {last[0]['content'][:200]}", importance=0.9, emotion=-0.5)
            self.mem.use_procedure("handle_mistake", success=True)
            if self.auto_skill:
                self._maybe_create_skill(text, last[0]["content"], correction)
        msg = "✅ Cảm ơn, tôi đã ghi nhận."
        if rating < 0:
            msg += " Tôi sẽ cẩn thận hơn với chủ đề này."
        return msg

    # ------------------ DREAM ------------------
    def dream(self):
        recent = self.mem.recall_episodes(limit=30, recent_only=True)
        if len(recent) < 3 and recent:
            recent = self.mem.recall_episodes(limit=30)
        try:
            semantics = self.mem.recall_semantics("", limit=80)
            mistakes = [dict(r) for r in self.mem.conn.execute(
                "SELECT content FROM episodes WHERE kind in ('mistake','self_qa_mistake') ORDER BY ts DESC LIMIT 10"
            ).fetchall()]
        except Exception:
            semantics = []
            mistakes = []
        buf = []
        for e in (recent[-20:] or [])[:10]:
            buf.append(f"- {e['content'][:160].replace(chr(10),' ')}")
        for s in semantics[:10]:
            buf.append(f"- fact: {s['fact'][:150]}")
        for m in mistakes[:10]:
            buf.append(f"- mistake: {m['content'][:160]}")
        ep_blob = "\n".join(buf) if buf else ""
        if len(buf) < 2:
            return {"summary": "Quá ít ký ức để tổng hợp.", "lessons": []}
        prompt = f"[MEMORY]{ep_blob}[/MEMORY]\nHãy tổng hợp ngắn gọn và rút 2-3 bài học, tránh lặp lại bài cũ."
        raw = self.brain.think(T_DREAM, prompt, temperature=0.6)
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else {"summary": raw[:200], "lessons": []}
        except Exception:
            data = {"summary": raw[:200], "lessons": []}
        lessons = data.get("lessons", [])
        for L in lessons:
            if isinstance(L, str) and len(L) > 10:
                self.mem.learn("lesson", L, confidence=0.6, source="dream")
        self.mem.add_dream(data.get("summary", ""), lessons)
        self.mem.remember_episode("dream", f"Tổng hợp: {data.get('summary','')} | Lessons: {len(lessons)}",
                                   importance=0.5, emotion=0.0)
        return data

    # ------------------ SKILLS ------------------
    def _maybe_create_skill(self, trigger, bad_answer, critique):
        prompt = f"[MISTAKE]Trigger: {trigger[:200]}\nBad answer: {bad_answer[:200]}\nCritique: {critique[:200]}[/MISTAKE]"
        raw = self.brain.think(T_SKILL, prompt, temperature=0.4)
        try:
            m = re.search(r"\{.*\}", raw, re.S)
            sk = json.loads(m.group(0)) if m else None
            if not sk or "name" not in sk or "steps" not in sk:
                return
            name = re.sub(r"\W+", "_", sk["name"].lower())[:40].strip("_")
            if not name:
                name = f"skill_{int(time.time())%10000}"
            existing = self.mem.list_procedures()
            if any(p["name"] == name for p in existing):
                return
            steps = sk["steps"] if isinstance(sk["steps"], list) else [sk["steps"]]
            self.mem.add_procedure(name, sk.get("description","Tự tạo từ kinh nghiệm lỗi"),
                                   steps, success_rate=0.4, auto_created=True)
            self.mem.remember_episode("new_skill", f"Đã tự tạo skill '{name}'", importance=0.7, emotion=0.3)
        except Exception:
            pass

    # ------------------ COMMANDS ------------------
    def _status_text(self):
        s = self.brain.status()
        st = None
        if _HAS_SCHEDULER and hasattr(self, "_study"):
            st = self._study.status()
        out = [
            "🧠 Brain     : " + s["backend"] + " — " + s["model"],
            "💾 Memory    : " + f"{self.mem.stats()['episodes']} episodes · {self.mem.stats()['semantics']} facts · {self.mem.stats()['procedures']} procedures",
            "🎯 Goals     : " + f"{self.mem.stats()['active_goals']} active / {self.mem.stats()['done_goals']} done",
            "💭 Dreams    : " + str(self.mem.stats()["dreams"]),
            "⏱️ Age       : " + f"{((time.time()-self.traits['born_at'])/3600):.1f}h · {self.turn_count} turns",
        ]
        if st:
            out.append("📚 Study     : " + f"running={st['running']} | due={st['due_reviews']} | today={st['logs_today']}")
        return "\n".join(out)

    def _export_knowledge(self):
        import datetime
        from memory import DB_DIR
        fn = DB_DIR / f"export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.mem.export_knowledge(str(fn))
        return f"💾 Đã xuất toàn bộ kiến thức ra: {fn}"

    def _commands_text(self):
        base = (
            "📝 Lệnh đặc biệt:\n"
            "  help / ?          trợ giúp\n"
            "  status            xem trạng thái nội bộ\n"
            "  goal <nội dung>   thêm mục tiêu tự chủ\n"
            "  forget <từ khóa>  quên kiến thức liên quan\n"
            "  dream             ép tổng hợp (ngủ mơ)\n"
            "  export            xuất toàn bộ kiến thức ra file JSON\n"
            "  nhớ: X là Y       dạy kiến thức mới\n"
            "  tốt / tệ vì ...   feedback để tôi học\n"
            "  check <chủ đề>    kiểm tra compliance/income\n"
            "  income_roadmap <status|add_focus|add_action|complete_action|set_execution_plan|clear>|<args>\n"
            "  income_focus <set_path|add_target|log|block_path|status>|<args>\n"
            "  income_opportunity_finder <query>   quét cơ hội thu nhập phù hợp\n"
            "  income_portfolio <add_platform|add_project|add_proposal|add_bounty|status|export>|<args>\n"
            "  quit              thoát\n"
            "Công cụ tôi tự dùng khi cần: calc, now, read, write, list, run_python, search"
        )
        if _HAS_SCHEDULER:
            base += (
                "\n\n📚 Học theo lịch:\n"
                "  study plan                 xem kế hoạch\n"
                "  study plan add <chủ đề>    thêm chủ đề học\n"
                "  study status               tiến độ / streak\n"
                "  study review today         ôn tập hôm nay\n"
                "  study weekly               tổng kết cuối tuần"
            )
        if _HAS_SELF_PATCHER:
            base += (
                "\n\n🔧 Tự nâng cấp:\n"
                "  patch <file>|<instruction>   đề xuất + áp patch\n"
                "  patch test <file>           smoke-test file\n"
                "  patch rollback <file>       rollback bản backup\n"
                "  patch backups               xem backup hiện có"
            )
        return base

    def _add_goal_from_text(self, text):
        goal = text[5:].strip()
        if not goal:
            return "Dùng: goal <nội dung>"
        self.mem.add_goal(goal, priority=0.7)
        return "🎯 Đã thêm mục tiêu mới."

    def _forget_from_text(self, text):
        q = text[7:].strip()
        if not q:
            return "Dùng: forget <từ khóa>"
        sems = self.mem.recall_semantics(q, limit=3)
        for s in sems:
            self.mem.forget(s["id"])
        return f"🗑️ Đã quên {len(sems)} mẩu kiến thức liên quan."

    def _compliance_check(self, text):
        try:
            from compliance import compliance_report, load_owner_policy
            topic = text[len("compliance"):].strip() or "dịch vụ AI giúp người và doanh nghiệp nhỏ tại Việt Nam"
            report = compliance_report(topic, load_owner_policy())
            return json.dumps(report, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"❌ Lỗi compliance: {e}"

    def _quick_check(self, text):
        try:
            from compliance import compliance_report, load_owner_policy
            topic = text[6:].strip()
            if not topic:
                return "Dùng: check <chủ đề kiếm tiền hoặc nghiệp vụ>"
            report = compliance_report(topic, load_owner_policy())
            short = [
                "compliance: " + topic,
                "legit_income=" + str(report["legit_income"]),
                "owner_aligned=" + str(report["owner_aligned"]),
                "income_score=" + str(report["income_score"]),
                "jurisdiction=" + str(report.get("jurisdiction_priority", "")),
                "locked=" + str(report.get("locked", False)),
            ]
            return "\n".join(short)
        except Exception as e:
            return f"❌ Lỗi check: {e}"

    def _income_roadmap(self, text):
        try:
            from skills_custom.active.income_roadmap import run as run_income_roadmap
            return run_income_roadmap(self, text)
        except Exception as e:
            return f"❌ Lỗi income_roadmap: {e}"

    def _income_focus(self, text):
        try:
            from skills_custom.active.income_focus import run as run_income_focus
            return run_income_focus(self, text)
        except Exception as e:
            return f"❌ Lỗi income_focus: {e}"

    def _income_opportunity_finder(self, text):
        try:
            from skills_custom.active.income_opportunity_finder import run as run_income_opp
            return run_income_opp(self, text)
        except Exception as e:
            return f"❌ Lỗi opportunity scan: {e}"

    def _income_portfolio(self, text):
        try:
            from skills_custom.active.income_portfolio import run as run_income_portfolio
            return run_income_portfolio(self, text)
        except Exception as e:
            return f"❌ Lỗi income_portfolio: {e}"

    def _help_text(self):
        s = self.status()
        base = (
            f"🤖 Xin chào! Tôi là {self.traits['name']}-AGI v{self.traits['version']}.\n"
            f"🧠 Backend: {s['brain']['backend']} ({s['brain']['model']})\n"
            f"💾 Trí nhớ: {s['memory']['episodes']} episodes, {s['memory']['semantics']} facts, "
            f"{s['memory']['procedures']} procedures (tự tạo {s['memory']['auto_procedures']})\n"
            f"🎯 Mục tiêu đang hoạt động: {s['memory']['active_goals']}\n"
            "\nTôi có thể: nhớ kiến thức, học từ feedback, tính toán, đọc/ghi file, chạy code Python, "
            "tự phản tỉnh và tự viết lại câu trả lời, tự tạo skill mới khi gặp lỗi, "
            "tự tổng hợp kiến thức khi 'ngủ mơ'.\n"
            "\nGrowth (opt-in):\n"
            "  review candidates        xem facts chờ duyệt\n"
            "  approve memory <id>      duyệt candidate → trusted\n"
            "  reject memory <id>       từ chối candidate\n"
            "  growth status            xem quota/state\n"
            "  growth report            xem báo cáo idle-study gần nhất\n"
            "\nGõ 'commands' để xem toàn bộ lệnh."
        )
        return base

    # ------------------ HELPERS ------------------
    def _detect_emotion(self, text):
        low = text.lower()
        pos = sum(w in low for w in ["cảm ơn","tốt","hay","yêu","vui","thích","tuyệt","ok","😊","👍","❤️","😂"])
        neg = sum(w in low for w in ["tệ","sai","bực","ghét","chán","buồn","khó chịu","giận","😡","😢","👎","dốt","kém"])
        return max(-1.0, min(1.0, (pos - neg) * 0.25))

    def _uncertainty(self, q, sem, epi):
        if sem or epi:
            cov = len(sem) + len(epi)
            c = max(0.15, 1 - 0.55 * min(cov, 6) / 6)
            return c
        if len(q) < 5:
            return 0.3
        return 0.85

    def _theory_of_mind(self, text):
        low = text.lower()
        intent = "unknown"
        need = "information"
        if any(k in low for k in ["làm ơn","giúp","help"]):
            intent = "request_help"
        elif any(k in low for k in ["?","hỏi","tại sao","làm sao","gì","ai","ở đâu"]):
            intent = "question"
        elif any(k in low for k in ["nhớ","học","ghi nhớ","note"]):
            intent = "teach"
        elif any(k in low for k in ["chào","hello","hi"]):
            intent = "greet"
        elif any(k in low for k in ["tốt","tệ","sai","hay"]):
            intent = "feedback"
        return {"intent": intent, "need": need}

    def _parse_plan(self, raw):
        try:
            cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.S).strip()
            m = re.search(r"\{.*\}", cleaned, re.S)
            if not m:
                return {"steps": cleaned.split("\n")[:6], "needs_tool": False, "tool_name": "none", "tool_args": ""}
            data = json.loads(m.group(0))
            steps = data.get("steps") if isinstance(data.get("steps"), list) else None
            tool_candidates = []
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict) and step.get("tool_name"):
                        tool_candidates.append(step)
                    elif isinstance(step, str) and " " in step.strip():
                        step_tool = step.split()[0].lower()
                        if step_tool in {"calc","read","write","list","run_python","search","now","help","none"}:
                            tool_candidates.append({"tool_name": step_tool, "tool_args": step.split(None, 1)[1]})
            tool_name = "none"
            tool_args = ""
            if tool_candidates:
                best = max(tool_candidates, key=lambda s: len((s.get("tool_args") or "").strip()))
                tool_name = best.get("tool_name") or "none"
                tool_args = best.get("tool_args") or tool_args
            if tool_name == "none":
                tool_name = data.get("tool_name", "none")
                tool_args = data.get("tool_args", "")
            needs_tool = bool(data.get("needs_tool")) or tool_name not in ("none", "")
            return {
                "steps": (steps or [str(data)])[:6],
                "needs_tool": needs_tool,
                "tool_name": tool_name or "none",
                "tool_args": tool_args or "",
            }
        except Exception:
            return {"steps": raw.split("\n")[:6], "needs_tool": False, "tool_name": "none", "tool_args": ""}

    def _forced_tool(self, text):
        low = text.lower()
        text = text.strip()
        if low.startswith("write "):
            arg = text[6:].strip()
            if "|" in arg.splitlines()[0]:
                return f"write {arg}"
            parts = arg.splitlines()[0].split(None, 1)
            if len(parts) == 2:
                return f"write {parts[0].strip()}|{parts[1].strip()}"
            return f"write {arg}"
        m = re.match(r"^(calc|read|write|list|run_python|search|now|help|python)\s+(.*)", text, re.I | re.S)
        if m:
            return f"{m.group(1).lower()} {m.group(2).strip()}"
        if re.search(r"^\s*tính\s+", low):
            expr = re.sub(r"^\s*tính\s+", "", text).strip("?.").strip()
            if re.match(r"^[\d\s\.\+\-\*\/\(\)\^%]+$", expr):
                return f"calc {expr}"
        if re.search(r"\d\s*[\+\-\*\/\^]\s*\d", text) and not re.search(r"[a-zA-Zà-ỹÀ-Ỵ]", text.split("?")[0]):
            m = re.search(r"[\d\s\.\+\-\*\/\(\)\^%]+", text)
            if m:
                return f"calc {m.group(0).strip()}"
        if re.search(r"(mấy giờ|giờ gì|ngày mấy|hôm nay)\b", low):
            return "now"
        return None

    def _extract_score(self, ref):
        m = re.search(r"(\d{1,2})\s*[/:]\s*10", ref)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        negs = ["chưa tốt","sai","thiếu","tệ","kém","yếu","lủng củng","vòng vo","quá ngắn"]
        pos = ["tốt","đầy đủ","chính xác","hợp lý","rõ ràng"]
        s = 5
        for w in negs:
            if w in ref.lower():
                s -= 1
        for w in pos:
            if w in ref.lower():
                s += 1
        return max(1, min(10, s))

    def _clean(self, ans):
        text = str(ans or "")
        text = re.sub(r"^```(?:json|python)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text, flags=re.M)
        return text.strip()

    def _compact_wm(self):
        out = []
        # Luôn giữ lại tin nhắn người dùng hiện tại nếu còn trong wm
        current_user = None
        for item in reversed(self.wm):
            if item.get("role") == "user" and current_user is None:
                current_user = item
        for item in self.wm[-8:]:
            role = item.get("role")
            content = item.get("content")
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False)
            out.append({"role": role, "content": content})
        if current_user is not None and not any(i.get("role") == "user" and i.get("content") == current_user.get("content") for i in out):
            out.insert(0, current_user)
        return out

    def _auto_learn(self, text, answer):
        if text.lower().startswith(("nhớ", "ghi nhớ", "học", "note")):
            m = re.match(r"^(nhớ|ghi nhớ|học|note)\s*[:\-]?\s*(.+)$", text, re.I)
            if m:
                fact = m.group(2).strip()
                self.mem.learn("user_taught", fact, confidence=0.8, source="user_taught")
                self.mem.remember_episode("learning", fact, importance=0.8, emotion=0.2)
        if re.match(r"^[A-Za-zÀ-ỹ0-9 _\-]{2,50}\s+(là|ở|thích|ghét|làm)\s+.+", text):
            # chặn học rác: không lưu nếu là câu hỏi
            q_end = text.strip().endswith("?")
            q_words = any(text.strip().lower().endswith(w) for w in ["gì", "sao", "nhỉ", "không?"])
            if not q_end and not q_words:
                self.mem.learn("user_statement", text, confidence=0.7, source="user_taught")
                self.mem.remember_episode("learning", text, importance=0.6, emotion=0.1)

    def _update_user_model(self, text, answer, emotion):
        m = re.search(r"(?:tôi )?(?:tên là|tên)\s+([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s]{1,20}?)(?:\.|,|$|\s+và|\s+ở|\s+từ|\s+tuổi|\s+làm)", text)
        if m:
            name = m.group(1).strip().split()[0]
            if len(name) > 1 and name.lower() not in ("gì","ai","là","bạn","clara"):
                self.mem.set_user("name", name, confidence=0.9)
                self.mem.learn("user_name", f"Người dùng tên là {name}", confidence=0.9, source="user_taught")
        m = re.search(r"tôi\s+(?:được\s+)?(\d{1,2})\s*tuổi", text)
        if m:
            self.mem.set_user("age", int(m.group(1)), confidence=0.8)
        m = re.search(r"(?:tôi )?(?:sống ở|ở|đến từ|quê ở|quê tôi ở)\s+([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s]{1,30}?)(?:\.|,|$|\s+và|\s+hiện|\s+tôi)", text)
        if m:
            loc = m.group(1).strip()
            self.mem.set_user("location", loc, confidence=0.75)
            self.mem.learn("user_location", f"Người dùng ở {loc}", confidence=0.75, source="user_taught")
        m = re.search(r"tôi\s+(?:là|làm)\s+(?:một\s+)?([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s]{1,25}?)(?:\.|,|$|\s+và|\s+tôi|\s+ở)", text)
        if m:
            job = m.group(1).strip()
            if job.lower() not in ("ai","gì","đây","đó","clara"):
                self.mem.set_user("job", job, confidence=0.7)
        likes = re.findall(r"tôi\s+(?:thích|yêu|hay\s+(?:uống|ăn|chơi|đọc|xem|nghe)|đam\s+mê)\s+([^.,;?!]+)", text, re.I)
        dislikes = re.findall(r"tôi\s+ghét\s+([^.,;?!]+)", text, re.I)
        q_words = {"gì", "sao", "nhỉ", "không", "ở đâu", "bao nhiêu", "khi nào", "tại sao"}
        is_question = text.strip().endswith("?") or any(text.strip().lower().endswith(w) for w in q_words)
        if likes or dislikes:
            if not is_question:
                for item in likes + dislikes:
                    item = item.strip()
                    if item and item.lower() not in q_words and len(item) >= 2:
                        key = "likes" if item in likes else "dislikes"
                        self.mem.set_user(key, [item], confidence=0.85, merge=True)
                        self.mem.learn("user_preference", f"Người dùng {'thích' if key=='likes' else 'ghét'} {item}", confidence=0.8, source="user_taught")
        if emotion < -0.3:
            self.traits["empathy"] = min(1.0, self.traits["empathy"] + 0.02)
            self.mem.set_trait("empathy", self.traits["empathy"])

    def _progress_goals(self, text, answer):
        goals = self.mem.get_active_goals(8)
        for g in goals:
            gl = g["goal"].lower()
            done = False
            if "tìm hiểu về người dùng" in gl:
                if len(self.mem.all_user()) >= 3:
                    done = True
            elif "cải thiện chất lượng" in gl:
                pass
            elif "học ít nhất 1 điều mới" in gl:
                sem_new = self.mem.recall_semantics(text, limit=1)
                if sem_new:
                    done = True
            if done:
                self.mem.complete_goal(g["id"])

    def _tags(self, text):
        tags = []
        keys = ["toán","code","python","nhớ","dạy","hỏi","chào","feedback","cảm xúc","tệp","file",
                "thời tiết","thời gian","tên","tuổi","địa điểm","ý kiến","kế hoạch","giúp"]
        low = text.lower()
        for k in keys:
            if k in low:
                tags.append(k)
        return tags

    def status(self):
        brain = self.brain.status()
        runtime = self._runtime_status()
        return {
            "brain": brain,
            "memory": self.mem.stats(),
            "traits": {k: (round(v,3) if isinstance(v,float) else v) for k,v in self.traits.items()},
            "workspace_size": len(self.wm),
            "age_hours": round((time.time()-self.traits["born_at"])/3600, 2),
            "turns": self.turn_count,
            "user_model_entries": len(self.mem.all_user()),
            "dreams": self.mem.stats()["dreams"],
            "recent_dreams": [{"ts": d["ts"], "summary": d["summary"][:80]}
                               for d in self.mem.recent_dreams(3)],
            "runtime": runtime,
        }

    def _runtime_status(self):
        try:
            from runtime_profile import governor_status
            rt = governor_status(self.profile_name, self.brain.model if self.brain.backend != "micro" else "micro-template", self.brain.backend)
            rt["language"] = self.language
            return rt
        except Exception as e:
            return {"profile": self.profile_name, "mode": "chat", "backend": self.brain.backend, "provider_model": self.brain.model, "language": self.language, "error": str(e)}

    def _review_candidates(self):
        rows = self.mem.review_candidates(limit=20)
        if not rows:
            return "📭 Không có candidate đang chờ duyệt."
        lines = [f"📋 Candidate ({len(rows)}):"]
        for r in rows:
            lines.append(f"  • id={r['id']} | {r['topic']} | src={r['source']} | conf={r['confidence']:.2f}")
        return "\n".join(lines)

    def _approve_memory(self, text):
        rest = text[len("approve memory"):].strip()
        if not rest or not rest.isdigit():
            return "Dùng: approve memory <id>"
        ok = self.mem.approve_candidate(int(rest))
        return "✅ Đã duyệt." if ok else "❌ Không tìm thấy id."

    def _reject_memory(self, text):
        rest = text[len("reject memory"):].strip()
        if not rest or not rest.isdigit():
            return "Dùng: reject memory <id>"
        ok = self.mem.reject_candidate(int(rest))
        return "🗑️ Đã từ chối." if ok else "❌ Không tìm thấy id."

    def _growth_status(self):
        st = self.mem.stats()
        try:
            from runtime_profile import governor_status
            rt = governor_status(self.profile_name, self.brain.model if self.brain.backend != "micro" else "micro-template", self.brain.backend)
        except Exception:
            rt = {"profile": self.profile_name, "mode": "chat", "degraded_reason": None}
        lines = [
            "📊 Growth status:",
            f"  profile={rt.get('profile')} mode={rt.get('mode')} degraded={rt.get('degraded_reason')} language={getattr(self, 'language', 'vi')}",
            f"  candidates pending={st.get('candidates_pending')} trusted={st.get('candidates_trusted')}",
            f"  idle_study enabled={bool(getattr(self, 'idle_study', False))} allow_network={bool(getattr(self, 'allow_network', False))}",
        ]
        return "\n".join(lines)

    def _growth_report(self):
        try:
            from pathlib import Path
            rpt = sorted((Path(__file__).resolve().parent / "data" / "growth_reports").glob("idle_study_*.json"))[-1]
            data = json.loads(rpt.read_text(encoding="utf-8"))
            return json.dumps({
                "profile": data.get("profile"),
                "mode": data.get("mode"),
                "degraded_reason": data.get("degraded_reason"),
                "used_session_minutes": data.get("used_session_minutes"),
                "topics": [t.get("topic") for t in data.get("topics", [])],
                "facts_candidate_count": len(data.get("facts_candidate", [])),
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"❌ Không đọc được report: {e}"

    def _language_feedback(self, text):
        rest = text[len("góp ý ngôn ngữ"):].strip()
        if not rest:
            return "Dùng: góp ý ngôn ngữ: <cách diễn đạt đúng/đẹp hơn>"
        self.mem.add_candidate(
            topic="language_feedback",
            fact=rest,
            source="user_language_feedback",
            confidence=0.7,
            reason="user language correction",
        )
        return "✅ Đã ghi nhận góp ý ngôn ngữ. Bạn có thể duyệt bằng 'review candidates' rồi 'approve memory <id>'."

    def _run_idle_study(self):
        try:
            from bounded_autolearn import run_idle_study_session
            report = run_idle_study_session(
                self,
                profile_name=getattr(self, "profile_name", "mobile_12gb_safe"),
                force=False,
                allow_network=bool(getattr(self, "allow_network", False)),
            )
            return json.dumps(report, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"❌ idle-study lỗi: {e}"
