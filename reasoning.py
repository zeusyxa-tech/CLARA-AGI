"""
CLARA-AGI v1.5 - Reasoning Engine: Chain-of-Thought + Reflection + Planner.
Cơ sở tư duy đa bước: think → plan (Planner DAG) → act → observe → reflect.
"""
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# Import PlanStep, StepStatus, Planner, Plan từ planner (gốc, không circular)
from planner import PlanStep, StepStatus, Planner, Plan


@dataclass
class ExecutionTrace:
    """Trace một lần thực thi plan."""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_id: Optional[str] = None
    final_result: str = ""
    success: bool = False
    iterations: int = 0

    def add_step(self, step: PlanStep):
        self.steps.append(step)

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def get_completed_results(self) -> Dict[str, Any]:
        """Lấy kết quả các step đã done để truyền cho step tiếp theo."""
        return {s.id: s.result for s in self.steps if s.status == StepStatus.DONE}

    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_id": self.current_step_id,
            "final_result": self.final_result,
            "success": self.success,
            "iterations": self.iterations,
        }


class ReasoningEngine:
    """
    Engine tư duy Chain-of-Thought cho CLARA.
    - Nhận goal + context (memory, tools available, working memory)
    - Sinh plan (DAG steps) qua LLM / Planner template
    - Validate plan trước khi chạy
    - Hỗ trợ reflection/replan khi step fail
    """

    def __init__(self, agi, max_steps: int = 10, max_retries: int = 2, temperature: float = 0.3):
        self.agi = agi
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.temperature = temperature
        self.trace: Optional[ExecutionTrace] = None
        self._step_counter = 0
        # Planner để dùng template + DAG validation + replan
        self.planner = Planner(agi, max_steps=max_steps, temperature=temperature)

    def _get_tools_dict(self) -> Dict:
        """Lấy dict công cụ từ agent."""
        return getattr(self.agi, "tools", {})

    # ========== PROMPT TEMPLATES ==========

    PLAN_PROMPT = """Bạn là bộ phân rã nhiệm vụ của CLARA-AGI.
Nhiệm vụ: {goal}

Ngữ cảnh:
- Working memory (gần đây): {wm_summary}
- Kiến thức liên quan (memory): {mem_summary}
- Công cụ có sẵn: {tools_list}
- Kết quả các bước trước (nếu replan): {prev_results}

YÊU CẦU:
1. Phân rã thành {max_steps} bước TỐI ĐA, mỗi bước dùng 1 công cụ.
2. Trả về JSON DUY NHẤT với cấu trúc:
{{
  "steps": [
    {{"id": "s1", "tool": "tool_name", "args": {{}...}}, "depends_on": [], "description": "mô tả ngắn"}},
    ...
  ]
}}
3. Chỉ dùng công cụ trong danh sách trên. Args phải khớp schema tool.
4. depends_on: list id các bước phải chạy trước (DAG).
5. Ưu tiên: search memory → web research → calc/read/write → run_python.
6. KHÔNG trả về text khác ngoài JSON.

Ví dụ tool args:
- search: {{"query": "RAG architecture"}}
- read: {{"path": "file.txt"}}
- write: {{"path": "out.txt", "content": "nội dung"}}
- calc: {{"expr": "sqrt(2)*2"}}
- run_python: {{"code": "print(1+1)"}}
- now: {{}}

JSON:"""

    REFLECT_PROMPT = """Bạn là bộ phản chiếu (reflection) của CLARA-AGI.
Mục tiêu gốc: {goal}
Bước vừa thực hiện: {step_desc}
Tool: {tool}, Args: {args}
Kết quả: {result}
Lỗi (nếu có): {error}
Kết quả các bước trước: {prev_results}

ĐÁNH GIÁ:
1. Bước này có đạt mục tiêu trung gian không?
2. Có cần sửa args / đổi tool / thêm bước không?
3. Có nên dừng sớm (đã đủ info) hay tiếp tục?

Trả về JSON DUY NHẤT:
{{
  "assessment": "success|partial|fail",
  "reason": "giải thích ngắn",
  "action": "continue|replan|stop",
  "suggested_fix": {{"tool": "...", "args": {{...}}}}  // nếu replan
}}"""

    FINALIZE_PROMPT = """Bạn là bộ tổng hợp kết quả của CLARA-AGI.
Mục tiêu: {goal}
Toàn bộ trace thực thi:
{trace_json}

Hãy tổng hợp thành câu trả lời cuối cùng cho người dùng:
- Tóm tắt những gì đã làm
- Kết quả chính (facts, files, numbers)
- Nếu còn thiếu: nêu rõ gì còn missing
- Tone: tự nhiên, tiếng Việt, helpful.

Trả về plain text (KHÔNG JSON)."""

    # ========== CORE METHODS ==========

    def think(self, goal: str, context: Optional[Dict] = None) -> ExecutionTrace:
        """
        Entry point: nhận goal, sinh plan, thực thi loop, trả về trace.
        """
        self.trace = ExecutionTrace(goal=goal)
        self._step_counter = 0
        trace = self.trace
        assert trace is not None

        # Build initial context
        ctx = self._build_context(context)

        # Initial planning
        plan_steps = self._generate_plan(goal, ctx)
        if not plan_steps:
            self.trace.final_result = "❌ Không sinh được plan."
            self.trace.success = False
            return self.trace

        for step in plan_steps:
            self.trace.add_step(step)

        # Execution loop
        return self._execute_loop(ctx)

    def _build_context(self, extra: Optional[Dict] = None) -> Dict:
        """Xây dựng context cho planning."""
        # Working memory summary
        wm = getattr(self.agi, "wm", [])
        wm_summary = ""
        if wm:
            recent = wm[-6:]  # last 3 exchanges
            wm_summary = "\n".join(
                f"{m.get('role', '?')}: {str(m.get('content', ''))[:120]} "
                for m in recent if isinstance(m, dict)
            )

        # Memory recall on goal
        mem_summary = ""
        if hasattr(self.agi, "mem"):
            try:
                hits = self.agi.mem.recall_semantics(extra.get("goal", "") if extra else "", limit=3)
                if hits:
                    mem_summary = "\n".join(f"- {h['fact'][:150]}" for h in hits)
            except Exception:
                pass

        # Available tools
        tools = self._get_tools_dict()
        tools_list = ", ".join(f"{k}({v.get('desc','')})" for k, v in tools.items())

        ctx = {
            "wm_summary": wm_summary or "(trống)",
            "mem_summary": mem_summary or "(chưa có kiến thức liên quan)",
            "tools_list": tools_list,
            "prev_results": "{}",
        }
        if extra:
            ctx.update(extra)
        return ctx

    def _generate_plan(self, goal: str, ctx: Dict) -> List[PlanStep]:
        """
        Sinh plan bằng Planner (template → LLM → DAG validate + auto-fix).
        Chỉ fallback LLM trực tiếp khi Planner không tạo được plan.
        """
        # BUILD context dict cho Planner.create_plan
        pctx = {
            "goal": goal,
            "_wm_summary": ctx.get("wm_summary", ""),
            "_mem_summary": ctx.get("mem_summary", ""),
            "_tools_list": ctx.get("tools_list", ""),
            "_prev_results": ctx.get("prev_results", "{}"),
        }
        plan = self.planner.create_plan(goal, context=pctx)
        if not plan or not plan.steps:
            return self._llm_generate_plan(goal, ctx)
        return plan.steps

    def _llm_generate_plan(self, goal: str, ctx: Dict) -> List[PlanStep]:
        """Fallback: gọi LLM raw sinh plan JSON."""
        prompt = self.PLAN_PROMPT.format(
            goal=goal,
            max_steps=self.max_steps,
            **ctx,
        )
        raw = self.agi.brain.think("__PLAN__", prompt, temperature=self.temperature)
        try:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                print(f"[DEBUG] No JSON found in LLM response: {raw[:200]}")
                return []
            data = json.loads(match.group(0))
            steps_data = data.get("steps", [])
            if not isinstance(steps_data, list):
                print(f"[DEBUG] steps_data is not a list: {type(steps_data)} = {steps_data}")
                return []
        except Exception as e:
            print(f"[DEBUG] JSON parse error: {e}, raw: {raw[:200]}")
            return []

        steps = []
        valid_tools = set(getattr(self.agi, "tools", {}).keys())
        for i, sd in enumerate(steps_data[:self.max_steps]):
            if not isinstance(sd, dict):
                print(f"[DEBUG] Step {i} is not a dict: {type(sd)} = {sd}")
                continue
            tool = sd.get("tool", "")
            if tool not in valid_tools:
                continue
            step = PlanStep(
                id=sd.get("id", f"s{i+1}"),
                tool=tool,
                args=sd.get("args", {}),
                depends_on=sd.get("depends_on", []),
                description=sd.get("description", ""),
            )
            steps.append(step)
        return steps

    def _execute_loop(self, ctx: Dict) -> ExecutionTrace:
        """Vòng lặp thực thi plan với reflection/retry."""
        trace = self.trace
        assert trace is not None
        completed = set()

        while True:
            # Tìm step tiếp theo ready to run
            next_step = self._get_next_ready_step(completed)
            if not next_step:
                break  # tất cả done hoặc blocked

            trace.current_step_id = next_step.id
            next_step.status = StepStatus.RUNNING

            # Execute step
            result = self._execute_step(next_step, ctx)

            # Reflection
            assessment = self._reflect(next_step, result, ctx)

            if assessment["assessment"] == "success":
                next_step.status = StepStatus.DONE
                next_step.result = result
                completed.add(next_step.id)
                ctx["prev_results"] = json.dumps(trace.get_completed_results(), ensure_ascii=False)
            elif assessment["assessment"] == "partial" and next_step.retry_count < self.max_retries:
                # Retry với suggested_fix
                next_step.retry_count += 1
                if assessment.get("suggested_fix"):
                    next_step.tool = assessment["suggested_fix"].get("tool", next_step.tool)
                    next_step.args = assessment["suggested_fix"].get("args", next_step.args)
                next_step.status = StepStatus.PENDING
                continue
            else:
                next_step.status = StepStatus.FAILED
                next_step.error = assessment.get("reason", "Unknown error")
                # Decide: replan or stop
                if assessment.get("action") == "replan" and trace.iterations < 2:
                    trace.iterations += 1
                    # Replan từ bước này trở đi
                    new_plan = self._replan_from_failure(next_step, ctx)
                    for ns in new_plan:
                        trace.add_step(ns)
                    continue
                break

        # Finalize
        trace.final_result = self._finalize(trace)
        trace.success = all(s.status == StepStatus.DONE for s in trace.steps)
        return trace

    def _get_next_ready_step(self, completed: set) -> Optional[PlanStep]:
        """Lấy step tiếp theo mà depends_on đã satisfied."""
        trace = self.trace
        assert trace is not None
        for step in trace.steps:
            if step.status == StepStatus.PENDING:
                deps = set(step.depends_on)
                if deps.issubset(completed):
                    return step
        return None

    def _execute_step(self, step: PlanStep, ctx: Dict) -> Any:
        """Thực thi 1 step, trả về result hoặc error string."""
        tool_name = step.tool
        args = step.args
        tools = getattr(self.agi, "tools", {})

        if tool_name not in tools:
            return f"❌ Tool không tồn tại: {tool_name}"

        tool_info = tools[tool_name]
        fn = tool_info["fn"]
        needs_agent = tool_info.get("needs_agent", False)

        try:
            if needs_agent:
                return fn(self.agi, args)
            else:
                # Handle args format
                if isinstance(args, dict):
                    # Flatten single arg
                    if len(args) == 1:
                        return fn(list(args.values())[0])
                    return fn(**args)
                return fn(args)
        except Exception as e:
            return f"❌ Lỗi thực thi {tool_name}: {e}"

    def _reflect(self, step: PlanStep, result: Any, ctx: Dict) -> Dict:
        """Gọi LLM phản chiếu kết quả step."""
        prompt = self.REFLECT_PROMPT.format(
            goal=self.trace.goal,
            step_desc=step.description,
            tool=step.tool,
            args=json.dumps(step.args, ensure_ascii=False),
            result=str(result)[:1500],
            error=step.error or "(không)",
            prev_results=ctx.get("prev_results", "{}"),
        )

        raw = self.agi.brain.think("__ANSWER__", prompt, temperature=0.2)

        try:
            match = re.search(r"\{.*\}", raw, re.S)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass

        # Default assessment
        if isinstance(result, str) and result.startswith("❌"):
            return {"assessment": "fail", "reason": str(result), "action": "stop"}
        return {"assessment": "success", "reason": "OK", "action": "continue"}

    def _replan_from_failure(self, failed_step: PlanStep, ctx: Dict) -> List[PlanStep]:
        """Sinh plan mới từ điểm fail."""
        trace = self.trace
        assert trace is not None
        # Mark failed step as skipped
        failed_step.status = StepStatus.SKIPPED

        # Build context with failure info
        ctx["prev_results"] = json.dumps(trace.get_completed_results(), ensure_ascii=False)
        ctx["failure_info"] = f"Bước {failed_step.id} ({failed_step.tool}) thất bại: {failed_step.error}"

        # Generate new plan for remaining goal
        remaining_goal = f"{trace.goal} (tiếp tục từ sau lỗi: {failed_step.description})"
        return self._generate_plan(remaining_goal, ctx)

    def _finalize(self, trace: ExecutionTrace) -> str:
        """Tổng hợp kết quả cuối cùng."""
        prompt = self.FINALIZE_PROMPT.format(
            goal=trace.goal,
            trace_json=json.dumps(trace.to_dict(), ensure_ascii=False, indent=2),
        )
        return self.agi.brain.think("__ANSWER__", prompt, temperature=0.4)


# ========== HELPER: Quick reasoning for simple queries ==========

def quick_reason(agi, query: str) -> str:
    """
    One-shot reasoning cho query đơn giản (không cần full loop).
    Dùng cho: "tính X", "tìm Y", "nhớ Z".
    """
    engine = ReasoningEngine(agi, max_steps=3, max_retries=1)
    trace = engine.think(query)
    return trace.final_result


# ========== EXPORTS ==========
__all__ = [
    "ReasoningEngine",
    "PlanStep",
    "ExecutionTrace",
    "StepStatus",
    "quick_reason",
]
