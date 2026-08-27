"""
CLARA-AGI - Main CLI Entry Point
Chạy agent, chế độ daemon, các lệnh quản lý (study, skill approval, status).
Tích hợp logging có cấu trúc.
"""
import sys
import os
import argparse
import json
import traceback

# Setup logging FIRST
import re
import time
from logging_utils import setup_logging, get_logger

logger = setup_logging("clara_cli")

from memory import Memory
from brain import Brain
from tools import parse_and_dispatch, TOOLS
from config import get_config, config

# Import optional modules gracefully
try:
    from scheduler import attach_study_commands, StudyScheduler
    _HAS_SCHEDULER = True
except Exception as e:
    _HAS_SCHEDULER = False
    logger.warning(f"Không tải được scheduler: {e}")

try:
    from self_improve import improve, list_pending, list_active, approve_skill, reject_skill
    _HAS_SELF_IMPROVE = True
except Exception as e:
    _HAS_SELF_IMPROVE = False
    logger.warning(f"Không tải được self_improve: {e}")

try:
    from autolearn import AutoLearner
    _HAS_AUTOLearn = True
except Exception as e:
    _HAS_AUTOLearn = False
    logger.warning(f"Không tải được autolearn: {e}")


class ClarasAGI:
    """Main agent class - giữ nguyên logic cũ nhưng dùng config mới."""

    def __init__(self, force_micro=False, model=None, dream_every=10, auto_skill=True):
        self.mem = Memory()
        self.brain = Brain(force_micro=force_micro, model=model)
        self.wm = []
        self.dream_every = dream_every
        self.auto_skill = auto_skill
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
        if _HAS_SCHEDULER:
            attach_study_commands(self)
            self._study = StudyScheduler(self, enabled=True, interval=config.section("scheduler").get("interval_seconds", 120))
            try:
                self._study.start()
            except Exception as e:
                logger.error(f"Không thể khởi tạo StudyScheduler: {e}")
                pass

    def _init_command_registry(self):
        """Register all command handlers."""
        # Auto-register tools from tools.TOOLS
        for tool_name, tool_def in TOOLS.items():
            if tool_name not in self._command_registry:
                self._command_registry[tool_name] = tool_def.get("fn", None)

    def _compact_wm(self):
        """Compact working memory to JSON-serializable form."""
        compact = []
        for entry in self.wm[-30:]:  # keep last 30 entries
            compact.append(entry)
        return compact

    def _handle_special_commands(self, text: str) -> str:
        """Xử lý các lệnh đặc biệt."""
        text_lower = text.lower().strip()
        
        # Commands
        if text_lower.startswith("/"):
            cmd_parts = text[1:].split()
            cmd = cmd_parts[0] if cmd_parts else ""
            
            if cmd == "status":
                return self._cmd_status()
            elif cmd == "approve" and len(cmd_parts) > 1:
                return approve_skill(cmd_parts[1])
            elif cmd == "reject" and len(cmd_parts) > 1:
                return reject_skill(cmd_parts[1])
            elif cmd == "skills":
                return self._cmd_skills()
            elif cmd == "clear":
                self.wm = []
                return "✅ Working memory cleared."
            elif cmd == "help":
                return self._cmd_help()
        
        return None

    def _cmd_status(self) -> str:
        """Trạng thái agent."""
        try:
            stats = self.mem.stats()
            brain_status = self.brain.status()
            active_goals = self.mem.get_active_goals(3)
            pending_skills = list_pending() if _HAS_SELF_IMPROVE else []
            active_skills = list_active() if _HAS_SELF_IMPROVE else []
            
            lines = [
                f"🧠 CLARA-AGI Status",
                f"  • Backend: {brain_status['backend']}",
                f"  • Model: {brain_status['model']}",
                f"  • Đã học episodes: {stats.get('episodes', 0)}",
                f"  • Đã ghi semantics: {stats.get('semantics', 0)}",
                f"  • Trạng thái hoạt động: {stats.get('active_goals', 0)} goals",
            ]
            
            if _HAS_SELF_IMPROVE:
                lines.append(f"  • Skills pending: {len(pending_skills)}")
                lines.append(f"  • Skills active: {len(active_skills)}")
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Lỗi _cmd_status: {e}")
            return f"❌ Lỗi lấy trạng thái: {e}"

    def _cmd_skills(self) -> str:
        """Danh sách skills."""
        if not _HAS_SELF_IMPROVE:
            return "❌ Self-improve module không khả dụng."
        
        active = list_active()
        pending = list_pending()
        
        lines = ["📋 Skills Catalog:"]
        
        if active:
            lines.append("\n✅ Active skills:")
            for s in active:
                lines.append(f"  • {s['file']} (stem: {s['stem']})")
        else:
            lines.append("\n✅ Active skills: (none)")
        
        if pending:
            lines.append(f"\n⏳ Pending skills: {len(pending)}:")
            for p in pending:
                lines.append(f"  • {p['file']}")
        else:
            lines.append(f"\n⏳ Pending skills: (none)")
        
        return "\n".join(lines)

    def _cmd_help(self) -> str:
        """Hỗ trợ lệnh."""
        lines = [
            "🤖 CLARA-AGI Commands:",
            "",
            "• `chào CLARA` / nhập tin nhắn thường - trò chuyện",
            "• `/status` - trạng thái agent",
            "• `/skills` - danh sách skills",
            "• `/approve <tên>` - kích hoạt skill pending",
            "• `/reject <tên>` - từ chối skill pending",
            "• `/clear` - xóa working memory",
            "• `/help` - trợ giúp này",
            "• `--once` - chạy 1 lần suy nghĩ",
            "• `--daemon` - chạy nền (auto-learn)",
            "",
            "Skill management:",
            "  - `approve <tên_file>`: Kích hoạt skill từ _pending/",
            "  - `reject <tên_file>`: Từ chối và xóa skill",
            "  - Skills tự tạo qua `improve` command",
        ]
        return "\n".join(lines)

    def chat(self, user_text: str) -> str:
        """Thông thường chat."""
        start = time.time()
        self.turn_count += 1
        self.mem.set_trait("turn_count", self.turn_count)
        text = user_text.strip()
        
        if not text:
            return "Bạn chưa nói gì 😊"
        
        special = self._handle_special_commands(text)
        if special is not None:
            return special
        
        # Log bắt đầu turn
        logger.info(f"Turn {self.turn_count}: received user input", 
                   extra={"user_text": text[:100] if len(text) > 100 else text})
        
        self.wm = [{"role": "user", "content": text}]
        
        # 1. PERCEIVE
        try:
            emotion = self._detect_emotion(text)
            self.wm.append({"role": "emotion", "content": emotion})
        except Exception as e:
            logger.warning(f"Emotion detect error: {e}")
            self.wm.append({"role": "emotion", "content": "neutral"})
        
        # Theory of Mind: nhìn nhận người dùng đang cần gì
        try:
            tom = self._theory_of_mind(text)
            self.wm.append({"role": "tom", "content": tom})
        except Exception as e:
            logger.warning(f"ToM error: {e}")
            self.wm.append({"role": "tom", "content": ""})
        
        # 2. RETRIEVE
        try:
            sem = self.mem.recall_semantics(text, limit=5)
            epi = self.mem.recall_episodes(text, limit=5)
            procs = self.mem.find_relevant_procedure(text)
            goals = self.mem.get_active_goals(4)
        except Exception as e:
            logger.error(f"Retrieve error: {e}")
            sem, epi, procs, goals = [], [], None, []
        
        if sem:
            self.wm.append({"role": "semantic_hits", "content": [s["fact"] for s in sem]})
        if epi:
            self.wm.append({"role": "episodic_hits", "content": [e["content"][:120] for e in epi]})
        if procs:
            self.wm.append({"role": "procedure", "content": {"name": procs["name"], "steps": procs["steps"][:200]}})
        if goals:
            self.wm.append({"role": "active_goals", "content": [g["goal"][:80] for g in goals]})
        
        # User model
        try:
            um = self.mem.all_user()
            if um:
                um_dict = {}
                for u in um[:6]:
                    try:
                        um_dict[u["k"]] = json.loads(u["v"])
                    except Exception:
                        um_dict[u["k"]] = u["v"]
                self.wm.append({"role": "user_model", "content": um_dict})
        except Exception as e:
            logger.warning(f"User model error: {e}")
        
        # Chat history
        if self.history:
            self.wm.append({"role": "chat_history", "content": self.history[-6:]})
        
        # 3. FEEL
        try:
            uncertainty = self._uncertainty(text, sem, epi)
            curiosity_bonus = self.traits["curiosity"] * 0.15
            uncertainty = min(1.0, uncertainty + curiosity_bonus - (0.1 if procs else 0))
            self.wm.append({"role": "uncertainty", "content": uncertainty})
        except Exception as e:
            logger.error(f"Feel error: {e}")
            self.wm.append({"role": "uncertainty", "content": 0.5})
        
        # 4. PLAN
        try:
            plan_prompt = f"Người dùng nói: {text}\n[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]"
            plan_raw = self.brain.think("__PLAN__", plan_prompt, temperature=0.3)
            plan = self._parse_plan(plan_raw)
            self.wm.append({"role": "plan", "content": plan})
        except Exception as e:
            logger.error(f"Plan error: {e}")
            self.wm.append({"role": "plan", "content": {"needs_tool": False, "tool_name": "none", "tool_args": ""}})
        
        # 5-6. TOOL + ACT
        try:
            tool_result = ""
            tool_used = "none"
            tool_args = plan.get("tool_args") or ""
            
            if plan.get("needs_tool") and tool_args and tool_args != "none":
                tool_result = parse_and_dispatch(self, tool_args)
                tool_used = plan.get("tool_name", tool_args.split()[0])
                self.mem.use_procedure("use_tool", success=("❌" not in tool_result and "Lỗi" not in tool_result))
            self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
        except Exception as e:
            logger.error(f"Tool dispatch error: {e}")
            self.wm.append({"role": "tool", "name": "none", "result": f"❌ Lỗi khi dùng tool: {str(e)[:200]}"})
        
        if tool_used == "none":
            forced = self._forced_tool(text)
            if forced:
                try:
                    tool_result = parse_and_dispatch(self, forced)
                    tool_used = forced.split()[0]
                    self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
                except Exception as e:
                    self.wm.append({"role": "tool", "name": "none", "result": f"❌ {e}"})
        
        if tool_used == "none":
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
                try:
                    next_raw = self.brain.think("__TOOL__", next_prompt, temperature=0.1, num_predict=120)
                    m = re.search(r"^(calc|read|write|list|run_python|search|now|help|none)\\s+(.*)", next_raw.strip(), re.S | re.I)
                    if not m:
                        break
                    next_tool = m.group(1).lower()
                    next_args = m.group(2).strip()
                    if next_tool == "none":
                        break
                    tool_result = parse_and_dispatch(self, f"{next_tool} {next_args}")
                    tool_used = next_tool
                    self.wm.append({"role": "tool", "name": tool_used, "result": tool_result[:600]})
                except Exception as e:
                    logger.error(f"Tool retry error: {e}")
                    self.wm.append({"role": "tool", "name": "none", "result": f"❌ {e}"})
                    tool_used = "none"
        
        # 7. REFLECT
        try:
            reflect_prompt = (
                f"Người dùng: {text}\n"
                f"[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]\n"
                f"[TOOL_RESULT]{tool_result or 'không dùng'}[/TOOL_RESULT]\n"
                "Phê bình câu trả lời: tìm lỗi, chỗ yếu, chỗ quá chung chung. "
                "Cho điểm trên thang 10. Trả lời ngắn gọn."
            )
            reflect_raw = self.brain.think("__REFLECT__", reflect_prompt, temperature=0.3)
            # Extract score
            score_match = re.search(r"(\d+(?:\.\d+)?)", reflect_raw.strip())
            reflect_score = float(score_match.group(1)) if score_match else 5.0
            
            # Reflect on tool result too
            if tool_used != "none":
                self.mem.use_procedure("use_tool", success=(reflect_score >= 5.0))
        except Exception as e:
            logger.warning(f"Reflect error: {e}")
            reflect_score = 5.0
        
        # 8. REWRITE
        try:
            rewrite_prompt = (
                f"Dựa trên lời phê bình (điểm {reflect_score}/10), "
                f"hãy viết lại câu trả lời sao cho tốt hơn. "
                f"Chỉ trả về câu trả lời mới bằng tiếng Việt, ngắn gọn (2-4 câu), không giải thích thêm.\n\n"
                f"Người dùng: {text}\n"
                f"[WORKSPACE]{json.dumps(self._compact_wm(), ensure_ascii=False)}[/WORKSPACE]\n"
                f"[TOOL_RESULT]{tool_result or 'không dùng'}[/TOOL_RESULT]"
            )
            rewrite_raw = self.brain.think("__REWRITE__", rewrite_prompt, temperature=0.3)
            answer = rewrite_raw.strip()
        except Exception as e:
            logger.error(f"Rewrite error: {e}")
            # Fallback: direct answer
            answer = self._direct_answer(text)
        
        # 9. ANSWER
        try:
            # Store in history
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": answer})
            # Keep history manageable
            if len(self.history) > 50:
                self.history = self.history[-50:]
            
            # Update traits
            if len(answer) > 10:
                self.mem.set_trait("verbosity", min(1.0, self.traits["verbosity"] + 0.01))
            
            # Persist memory (học "nhớ:", cập nhật user model, lưu episode)
            try:
                self._persist_memory(text, answer)
            except Exception as e:
                logger.warning(f"Persist memory lỗi: {e}")
            
            elapsed = time.time() - start
            logger.info(f"Turn {self.turn_count}: answering in {elapsed:.2f}s", 
                       extra={"response_len": len(answer), "tool_used": tool_used, "elapsed": elapsed})
            
            return answer
        except Exception as e:
            logger.error(f"Answer error: {e}")
            traceback_str = traceback.format_exc()
            logger.critical(traceback_str)
            return f"❌ CLARA đang gặp sự cố kỹ thuật. Vui lòng thử lại sau."
    
    def _persist_memory(self, text: str, answer: str):
        """Lưu trí nhớ sau mỗi turn: học 'nhớ:', cập nhật user model, ghi episode."""
        low = text.lower().strip()

        # 1. Học kiến thức từ "nhớ:/học:/ghi nhớ:/note:"
        if low.startswith(("nhớ", "ghi nhớ", "học", "note")):
            m = re.match(r"^(nhớ|ghi nhớ|học|note)\s*[:\-]?\s*(.+)$", text, re.I)
            if m:
                fact = m.group(2).strip()
                self.mem.learn("user_taught", fact, confidence=0.8, source="user_taught")
                self.mem.remember_episode("learning", fact, importance=0.8, emotion=0.2)

        # 2. Cập nhật user model từ các mẫu quen thuộc
        # tên: "tôi tên Nam" / "tên tôi là Nam"
        m_name = re.search(r"(?:tôi\s*tên|tên\s*tôi\s*(?:là|tên)?)\s*([A-ZÀ-Ỹ][a-zà-ỹ]*)", text, re.I)
        if m_name:
            self.mem.set_user("name", m_name.group(1), confidence=0.9)
            self.mem.learn("user_name", f"Người dùng tên là {m_name.group(1)}", confidence=0.9, source="user_taught")
        # thích: "thích lập trình Python"
        m_like = re.search(r"thích\s+([^,.!?]+)", text, re.I)
        if m_like:
            item = m_like.group(1).strip()
            self.mem.set_user("likes", [item], confidence=0.85, merge=True)
            self.mem.learn("user_preference", f"Người dùng thích {item}", confidence=0.8, source="user_taught")

        # 3. Luôn lưu episode hội thoại (cho episodic memory / dream)
        self.mem.remember_episode("conversation", f"User: {text}\nCLARA: {answer}",
                                  importance=0.4, emotion=0.0)

    def _detect_emotion(self, text: str) -> str:
        """Phát hiện cảm xúc đơn giản."""
        text_lower = text.lower()
        if any(k in text_lower for k in ["đau", "buồn", "thất", "sorry", "xin lỗi"]):
            return "sad"
        elif any(k in text_lower for k in ["vui", "happy", "yah", "wow", "great"]):
            return "happy"
        elif any(k in text_lower for k in ["tăng lên", "giúp", "cần help"]):
            return "asking"
        return "neutral"
    
    def _theory_of_mind(self, text: str) -> str:
        """Nhìn nhận người dùng đang cần gì."""
        text_lower = text.lower()
        if "tên tôi" in text_lower or "tôi tên" in text_lower:
            return "User hỏi tên của chính mình (từ user model)"
        elif any(k in text_lower for k in ["làm sao", "cách làm", "hướng dẫn"]):
            return "User cần hướng dẫn/giải pháp"
        elif any(k in text_lower for k in ["tại sao", "ký rệ"]):
            return "User muốn hiểu nguyên nhân"
        return "User giao tiếp thông thường"
    
    def _uncertainty(self, text: str, sem: list, epi: list) -> float:
        """Tính mức độ không chắc chắn."""
        # Nếu có semantic hits + không có episodic -> khá chắc
        if sem and not epi:
            return 0.3
        # Nếu không có gì -> rất chắc
        if not sem and not epi:
            return 0.1
        # Nếu có episodic -> đang xử lý
        if epi:
            return 0.5
        return 0.7
    
    def _parse_plan(self, plan_raw: str) -> dict:
        """Phân tích kế hoạch từ đầu ra Brain."""
        try:
            # Try JSON parse first
            plan = json.loads(plan_raw.strip())
            if isinstance(plan, dict):
                # Ensure required keys
                plan.setdefault("needs_tool", False)
                plan.setdefault("tool_name", "none")
                plan.setdefault("tool_args", "")
                return plan
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: parse by patterns
        plan = {"needs_tool": False, "tool_name": "none", "tool_args": ""}
        
        # Check for tool patterns
        tool_match = re.search(r'(calc|read|write|list|run_python|search|now|help)\s+(.*)', plan_raw.strip())
        if tool_match:
            plan["needs_tool"] = True
            plan["tool_name"] = tool_match.group(1)
            plan["tool_args"] = tool_match.group(2).strip()
            return plan
        
        # Check JSON-like
        json_match = re.search(r'\{.*\}', plan_raw.strip(), re.S)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    plan.update(parsed)
                    plan.setdefault("needs_tool", False)
                    plan.setdefault("tool_name", "none")
                    plan.setdefault("tool_args", "")
                    return plan
            except (json.JSONDecodeError, ValueError):
                pass
        
        return plan
    
    def _forced_tool(self, text: str) -> str:
        """Làm power tool khi user rõ ràng muốn dùng tool."""
        text_lower = text.lower()
        if any(k in text_lower for k in ["tính", "plus", "minus", "nhân", "chia", "mũ"]):
            return f"calc {text}"
        elif any(k in text_lower for k in ["tìm", "search", "google", "web"]):
            # Extract query after search keywords
            for kw in ["tìm ", "search ", "web "]:
                if kw in text_lower:
                    query = text_lower.split(kw, 1)[1].strip()
                    return f"search {query}"
                    break
        elif any(k in text_lower for k in ["đọc", "read", "file"]):
            # Extract filename
            import re
            match = re.search(r'read\s+(.+)', text_lower)
            if match:
                return f"read {match.group(1).strip()}"
        return None
    
    def _direct_answer(self, text: str) -> str:
        """Trả lời trực tiếp khi rewrite fail."""
        # Check if we have relevant memories
        try:
            sem = self.mem.recall_semantics(text, limit=3)
            if sem:
                # Return summary of relevant facts
                facts = [s["fact"] for s in sem[:2]]
                return f"Tôi nhớ rằng: {'; '.join(facts)}"
        except Exception:
            pass
        return f"CLARA đang suy nghĩ về: {text[:80]}..."


def _setup_agent(args):
    """Khởi tạo agent (và các thread autolearn/self-improve nếu được yêu cầu)."""
    agent = ClarasAGI(force_micro=args.micro, model=args.model)
    threads = []

    # Auto-learn (tự học khi rảnh)
    if args.auto_learn and _HAS_AUTOLearn:
        try:
            auto = AutoLearner(agent, interval=config.section("autolearner").get("interval_seconds", 25), verbose=True)
            auto.start()
            threads.append(auto)
            logger.info("AutoLearner started")
        except Exception as e:
            logger.warning(f"Không khởi được AutoLearner: {e}")

    # Self-improve (tự nghiên cứu web học thêm)
    if args.self_improve and _HAS_SELF_IMPROVE:
        try:
            from self_improve import load_custom_skills, research
            loaded = load_custom_skills(agent)
            if loaded:
                logger.info(f"Đã nạp {len(loaded)} skill tự tạo: {', '.join(loaded)}")
            import threading
            improver_running = {"on": True}
            topics = [
                "python useful utility function example",
                "cách tính chiết khấu phần trăm trong Python",
                "python convert between units",
                "simple data validation python function",
                "cách đếm số ngày giữa hai ngày trong Python",
                "cách tạo mật khẩu ngẫu nhiên an toàn Python",
                "python text processing tips",
                "cách tính chỉ số BMI Python",
            ]
            research_interval = config.section("self_improve").get("max_pages_research", 3)

            def _research_loop():
                import random
                time.sleep(15)
                while improver_running["on"]:
                    try:
                        topic = random.choice(topics)
                        logger.info(f"[tự nâng cấp] đang nghiên cứu: {topic}")
                        research(agent, topic, max_pages=1)
                        logger.info(f"[tự nâng cấp] đã học xong '{topic}'")
                    except Exception as e:
                        logger.warning(f"[tự nâng cấp] lỗi: {e}")
                    for _ in range(research_interval):
                        if not improver_running["on"]:
                            return
                        time.sleep(1)

            t = threading.Thread(target=_research_loop, daemon=True)
            t.start()
            threads.append(("self_improve", improver_running))
            logger.info("Self-improve research loop started")
        except Exception as e:
            logger.warning(f"Không khởi được self-improve: {e}")

    return agent, threads


def _interactive_loop(agent):
    """Vòng lặp chat tương tác."""
    print("🤖 CLARA-AGI sẵn sàng! Gõ 'help' để xem lệnh.")
    print("💡 Gõ `/help` trong hội thoại để xem trợ giúp.")
    print("• Ctrl+C để thoát\n")
    try:
        while True:
            try:
                user_input = input("CLARA> ").strip()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    result = agent._handle_special_commands(user_input)
                    if result:
                        print(result)
                    continue
                result = agent.chat(user_input)
                print(result)
            except KeyboardInterrupt:
                print("\n👋 Tạm biệt!")
                break
            except EOFError:
                # Hết input (vd: pipe stdin vào) -> thoát sạch, không lặp vô tận
                print("\n👋 Tạm biệt!")
                break
            except Exception as e:
                logger.error(f"Chat error: {e}")
                print(f"❌ Lỗi: {e}")
    except KeyboardInterrupt:
        print("\n👋 Tạm biệt!")


def main():
    """CLI entry point.

    Cú pháp:
      python main.py                         -> chat tương tác
      python main.py chat "câu hỏi"          -> chat 1 lần (in kết quả)
      python main.py --once "câu hỏi"        -> chat 1 lần (cho daemon/testing)
      python main.py status                  -> in trạng thái
      python main.py skills                  -> danh sách skills
      python main.py help                    -> trợ giúp
      python main.py --web                   -> giao diện web (cần flask)
      python main.py --auto-learn            -> tự học nền
      python main.py --self-improve          -> tự nghiên cứu web
      python main.py --micro                 -> ép dùng micro brain
      python main.py --model qwen2.5:3b      -> chọn model
    """
    parser = argparse.ArgumentParser(
        description="CLARA-AGI v1.4 - Agent tự chủ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Optional flags (giữ cú pháp --once "..." đã ghi trong doc)
    parser.add_argument("--once", nargs="+", metavar="TEXT", help="Chạy 1 lần suy nghĩ rồi thoát")
    parser.add_argument("--daemon", action="store_true", help="Chạy daemon (in sẵn sàng, không block)")
    parser.add_argument("--auto-learn", action="store_true", help="Bật tự học khi rảnh (AutoLearner)")
    parser.add_argument("--self-improve", action="store_true", help="Bật tự nghiên cứu web học thêm")
    parser.add_argument("--web", action="store_true", help="Chạy giao diện web (cần flask)")
    parser.add_argument("--micro", action="store_true", help="Ép dùng micro brain (không cần Ollama)")
    parser.add_argument("--model", default=None, help="Chọn model Ollama (vd: qwen2.5:3b)")
    # Positional command (chat/status/skills/help) + phần còn lại làm args
    parser.add_argument("command", nargs="?", default="chat",
                        choices=["chat", "status", "skills", "help"],
                        help="Lệnh (mặc định: chat)")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Tham số cho lệnh (vd: chat 'câu hỏi')")

    try:
        args = parser.parse_args()

        # --once có quyền ưu tiên cao nhất
        if args.once:
            agent = ClarasAGI(force_micro=args.micro, model=args.model)
            user_text = " ".join(args.once)
            result = agent.chat(user_text)
            print(result)
            return

        # Khởi agent (+ threads nếu có)
        agent, threads = _setup_agent(args)

        # --daemon: in sẵn sàng rồi giữ process sống (threads nền chạy tiếp)
        if args.daemon:
            logger.info("CLARA-AGI daemon started")
            print("✅ CLARA-AGI daemon đang chạy...")
            print("• Dùng `python main.py --once \"câu hỏi\"` để test")
            print("• Dùng `/status` trong chat để xem trạng thái")
            print("• Ctrl+C để dừng daemon")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("CLARA-AGI daemon stopped")
                print("\n👋 Daemon dừng.")
            return

        # --web: giao diện web
        if args.web:
            try:
                from webui import run_web
                run_web(agent)
            except Exception as e:
                logger.error(f"Web UI lỗi: {e}")
                print(f"❌ Không chạy được Web UI: {e}\n(Cần cài flask: pip install flask)")
            return

        # Lệnh positional
        if args.command == "status":
            print(agent._cmd_status())
        elif args.command == "skills":
            print(agent._cmd_skills())
        elif args.command == "help":
            print(agent._cmd_help())
        elif args.command == "chat":
            if args.args:
                user_text = " ".join(args.args)
                result = agent.chat(user_text)
                print(result)
            else:
                _interactive_loop(agent)

    except KeyboardInterrupt:
        print("\n👋 Tạm biệt!")
    except Exception as e:
        logger.critical(f"Fatal error in main(): {e}", exc_info=True)
        print(f"❌ CLARA-AGI gặp lỗi nghiêm trọng:\n{e}")
        print("Xem logs tại: logs/clara.log")


if __name__ == "__main__":
    main()