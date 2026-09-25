"""
CLARA-AGI v1.5 - Planner: Task Decomposition into DAG Steps.
Nhận goal phức tạp → sinh DAG các step có depends_on → topological sort để thực thi.
"""
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum


# ========== DOMAIN MODEL (gốc, không circular) ==========
class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Một bước trong plan thực thi."""
    id: str
    tool: str
    args: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    retry_count: int = 0

    def to_dict(self) -> Dict:
        d = {
            "id": self.id,
            "tool": self.tool,
            "args": self.args,
            "depends_on": self.depends_on,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
        }
        return d


@dataclass
class Plan:
    """Một plan hoàn chỉnh với DAG steps."""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: PlanStep):
        self.steps.append(step)

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def validate_dag(self) -> Tuple[bool, str]:
        """Kiểm tra DAG không có cycle, depends_on hợp lệ."""
        ids = {s.id for s in self.steps}
        # Check all depends_on exist
        for s in self.steps:
            for dep in s.depends_on:
                if dep not in ids:
                    return False, f"Step {s.id} depends_on không tồn tại: {dep}"

        # Check cycle using Kahn's algorithm
        in_degree = {s.id: 0 for s in self.steps}
        adj = defaultdict(list)
        for s in self.steps:
            for dep in s.depends_on:
                adj[dep].append(s.id)
                in_degree[s.id] += 1

        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited = 0
        while queue:
            u = queue.popleft()
            visited += 1
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if visited != len(self.steps):
            return False, "DAG có cycle (circular dependency)"

        return True, "OK"

    def topological_order(self) -> List[PlanStep]:
        """Trả về steps theo thứ tự topological (sẵn sàng chạy)."""
        in_degree = {s.id: 0 for s in self.steps}
        adj = defaultdict(list)
        for s in self.steps:
            for dep in s.depends_on:
                adj[dep].append(s.id)
                in_degree[s.id] += 1

        queue = deque([s for s in self.steps if in_degree[s.id] == 0])
        result = []
        while queue:
            u = queue.popleft()
            result.append(u)
            for v_id in adj[u.id]:
                in_degree[v_id] -= 1
                if in_degree[v_id] == 0:
                    v_step = self.get_step(v_id)
                    if v_step:
                        queue.append(v_step)
        return result

    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }


class Planner:
    """
    Planner phân rã goal thành DAG steps.
    - Dùng LLM để sinh plan ban đầu
    - Validate DAG
    - Hỗ trợ replan khi có failure
    - Template-based cho các pattern phổ biến
    """

    def __init__(self, agi, max_steps: int = 12, temperature: float = 0.3):
        self.agi = agi
        self.max_steps = max_steps
        self.temperature = temperature
        self._templates = self._load_templates()

    # ========== TEMPLATES FOR COMMON PATTERNS ==========

    def _load_templates(self) -> Dict[str, Dict]:
        """Template plan cho các pattern thường gặp."""
        return {
            "research": {
                "keywords": ["nghiên cứu", "research", "tìm hiểu", "tìm paper", "tìm bài viết", "survey"],
                "steps": [
                    {"id": "s1", "tool": "search", "args": {"query": "{goal}"}, "depends_on": [], "description": "Tìm trong memory"},
                    {"id": "s2", "tool": "search", "args": {"query": "{goal}"}, "depends_on": ["s1"], "description": "Web search"},
                    {"id": "s3", "tool": "read", "args": {"path": "{s2_result_url_1}"}, "depends_on": ["s2"], "description": "Đọc trang đầu"},
                    {"id": "s4", "tool": "read", "args": {"path": "{s2_result_url_2}"}, "depends_on": ["s2"], "description": "Đọc trang thứ 2"},
                    {"id": "s5", "tool": "run_python", "args": {"code": "summary = '...'\nprint(summary)"}, "depends_on": ["s3", "s4"], "description": "Tóm tắt kết quả"},
                ],
            },
            "calculate": {
                "keywords": ["tính", "calc", "biểu thức", "giải phương trình", "compute"],
                "steps": [
                    {"id": "s1", "tool": "calc", "args": {"expr": "{goal}"}, "depends_on": [], "description": "Tính toán"},
                ],
            },
            "file_ops": {
                "keywords": ["đọc file", "ghi file", "tạo file", "xóa file", "list file", "read file", "write file"],
                "steps": [
                    {"id": "s1", "tool": "list", "args": {"path": "."}, "depends_on": [], "description": "Liệt kê workspace"},
                    {"id": "s2", "tool": "read", "args": {"path": "{target_file}"}, "depends_on": ["s1"], "description": "Đọc file"},
                    {"id": "s3", "tool": "write", "args": {"path": "{output_file}", "content": "{content}"}, "depends_on": ["s2"], "description": "Ghi file"},
                ],
            },
            "code_task": {
                "keywords": ["code", "lập trình", "viết code", "debug", "sửa lỗi", "refactor", "python"],
                "steps": [
                    {"id": "s1", "tool": "search", "args": {"query": "{goal}"}, "depends_on": [], "description": "Tìm kiến thức liên quan"},
                    {"id": "s2", "tool": "run_python", "args": {"code": "{prototype_code}"}, "depends_on": ["s1"], "description": "Prototype/test code"},
                    {"id": "s3", "tool": "write", "args": {"path": "{output_file}", "content": "{final_code}"}, "depends_on": ["s2"], "description": "Lưu code cuối"},
                ],
            },
            "memory_task": {
                "keywords": ["nhớ", "ghi nhớ", "lưu", "học", "learn", "remember"],
                "steps": [
                    {"id": "s1", "tool": "search", "args": {"query": "{goal}"}, "depends_on": [], "description": "Kiểm tra đã biết chưa"},
                    {"id": "s2", "tool": "run_python", "args": {"code": "agi.mem.learn('topic', 'fact', confidence=0.8)"}, "depends_on": ["s1"], "description": "Lưu vào memory"},
                ],
            },
        }

    # ========== MAIN PLANNING METHODS ==========

    def create_plan(self, goal: str, context: Optional[Dict] = None) -> Plan:
        """
        Tạo plan từ goal.
        1. Thử match template
        2. Nếu không match → gọi LLM sinh plan
        3. Validate & return Plan object
        """
        # 1. Try template match
        template_plan = self._match_template(goal)
        if template_plan:
            plan = self._instantiate_template(template_plan, goal, context)
            valid, msg = plan.validate_dag()
            if valid:
                return plan

        # 2. LLM-based planning
        plan = self._llm_plan(goal, context)
        valid, msg = plan.validate_dag()
        if not valid:
            # Auto-fix: remove invalid depends_on
            plan = self._auto_fix_plan(plan)
            valid, msg = plan.validate_dag()

        return plan

    def _match_template(self, goal: str) -> Optional[Dict]:
        """Match goal với template dựa trên keywords."""
        low = goal.lower()
        for name, tmpl in self._templates.items():
            for kw in tmpl["keywords"]:
                if kw in low:
                    return tmpl
        return None

    def _instantiate_template(self, template: Dict, goal: str, context: Optional[Dict]) -> Plan:
        """Điền goal/context vào template steps."""
        plan = Plan(goal=goal)
        for step_tmpl in template["steps"]:
            # Simple placeholder replacement
            args = step_tmpl["args"].copy()
            for k, v in args.items():
                if isinstance(v, str):
                    args[k] = v.replace("{goal}", goal)
                    if context:
                        for ck, cv in context.items():
                            args[k] = args[k].replace(f"{{{ck}}}", str(cv))
            step = PlanStep(
                id=step_tmpl["id"],
                tool=step_tmpl["tool"],
                args=args,
                depends_on=step_tmpl["depends_on"],
                description=step_tmpl["description"],
            )
            plan.add_step(step)
        return plan

    def _llm_plan(self, goal: str, context: Optional[Dict] = None) -> Plan:
        """Gọi LLM sinh plan JSON."""
        # Build context similar to ReasoningEngine
        wm = getattr(self.agi, "wm", [])
        wm_summary = "\n".join(f"{m['role']}: {m['content'][:120]}" for m in wm[-6:]) if wm else "(trống)"

        mem_summary = ""
        if hasattr(self.agi, "mem"):
            try:
                hits = self.agi.mem.recall_semantics(goal, limit=3)
                if hits:
                    mem_summary = "\n".join(f"- {h['fact'][:150]}" for h in hits)
            except Exception:
                pass
        mem_summary = mem_summary or "(chưa có kiến thức liên quan)"

        tools = getattr(self.agi, "tools", {})
        tools_list = ", ".join(f"{k}({v.get('desc','')})" for k, v in tools.items())

        prompt = f"""Bạn là Planner của CLARA-AGI. Phân rã mục tiêu thành DAG steps.

Mục tiêu: {goal}

Ngữ cảnh:
- Working memory: {wm_summary}
- Memory: {mem_summary}
- Tools: {tools_list}

YÊU CẦU:
1. Tối đa {self.max_steps} bước.
2. Trả về JSON DUY NHẤT:
{{
  "steps": [
    {{"id": "s1", "tool": "tool_name", "args": {{...}}, "depends_on": [], "description": "mô tả"}},
    ...
  ]
}}
3. depends_on: tạo DAG (không cycle). Steps độc lập có thể song song (depends_on=[]).
4. Args phải đúng schema tool.
5. Ưu tiên: search → read/web → calc/write/run_python.

JSON:"""

        raw = self.agi.brain.think("__PLAN__", prompt, temperature=self.temperature)

        try:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                return self._fallback_plan(goal)
            data = json.loads(match.group(0))
            steps_data = data.get("steps", [])
        except Exception:
            return self._fallback_plan(goal)

        plan = Plan(goal=goal)
        valid_tools = set(tools.keys())
        for i, sd in enumerate(steps_data[:self.max_steps]):
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
            plan.add_step(step)
        return plan

    def _fallback_plan(self, goal: str) -> Plan:
        """Fallback plan đơn giản."""
        plan = Plan(goal=goal)
        low = goal.lower()

        if any(k in low for k in ["tính", "calc", "biểu thức"]):
            plan.add_step(PlanStep(id="s1", tool="calc", args={"expr": goal}, description="Tính toán"))
        elif any(k in low for k in ["tìm", "search", "nghiên cứu"]):
            plan.add_step(PlanStep(id="s1", tool="search", args={"query": goal}, description="Tìm memory"))
            plan.add_step(PlanStep(id="s2", tool="search", args={"query": goal}, depends_on=["s1"], description="Web search"))
        else:
            plan.add_step(PlanStep(id="s1", tool="search", args={"query": goal}, description="Tìm kiếm"))

        return plan

    def _auto_fix_plan(self, plan: Plan) -> Plan:
        """Tự sửa plan: bỏ depends_on invalid, dedup IDs."""
        # Dedup IDs
        seen = set()
        for s in plan.steps:
            if s.id in seen:
                # Generate new ID
                base = s.id
                i = 2
                while f"{base}_{i}" in seen:
                    i += 1
                s.id = f"{base}_{i}"
            seen.add(s.id)

        # Remove invalid depends_on
        valid_ids = {s.id for s in plan.steps}
        for s in plan.steps:
            s.depends_on = [d for d in s.depends_on if d in valid_ids]

        return plan

    def replan(self, failed_step: PlanStep, completed_results: Dict, original_goal: str) -> Plan:
        """
        Replan từ một bước thất bại.
        - Giữ các step đã done
        - Sinh plan mới cho phần còn lại
        """
        # Build context with failure info
        ctx = {
            "completed_results": json.dumps(completed_results, ensure_ascii=False),
            "failed_step": f"{failed_step.id} ({failed_step.tool}): {failed_step.error}",
            "original_goal": original_goal,
        }

        prompt = f"""Bạn là Planner của CLARA-AGI. Replan sau khi có bước thất bại.

Mục tiêu gốc: {original_goal}
Bước thất bại: {failed_step.id} - {failed_step.tool} - {failed_step.error}
Kết quả đã hoàn thành: {json.dumps(completed_results, ensure_ascii=False)}

Hãy sinh plan MỚI cho phần CÒN LẠI (chỉ các bước chưa làm).
Trả về JSON DUY NHẤT với cấu trúc steps như trước.
Các step đã done KHÔNG được lặp lại.

JSON:"""

        raw = self.agi.brain.think("__PLAN__", prompt, temperature=self.temperature)

        try:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                return Plan(goal=original_goal)  # empty plan
            data = json.loads(match.group(0))
            steps_data = data.get("steps", [])
        except Exception:
            return Plan(goal=original_goal)

        new_plan = Plan(goal=original_goal)
        valid_tools = set(getattr(self.agi, "tools", {}).keys())
        for i, sd in enumerate(steps_data[:self.max_steps]):
            tool = sd.get("tool", "")
            if tool not in valid_tools:
                continue
            step = PlanStep(
                id=sd.get("id", f"r{i+1}"),  # prefix 'r' for replan
                tool=tool,
                args=sd.get("args", {}),
                depends_on=sd.get("depends_on", []),
                description=sd.get("description", ""),
            )
            new_plan.add_step(step)

        return new_plan


# ========== UTILITIES ==========

def merge_plans(base: Plan, additional: Plan, connect_to: Optional[str] = None) -> Plan:
    """Gộp 2 plan, nối additional vào base tại step connect_to."""
    merged = Plan(goal=base.goal)
    # Copy base steps
    for s in base.steps:
        merged.add_step(s)
    # Add additional steps with updated IDs
    id_map = {}
    for s in additional.steps:
        new_id = f"a_{s.id}"
        id_map[s.id] = new_id
        new_step = PlanStep(
            id=new_id,
            tool=s.tool,
            args=s.args,
            depends_on=[id_map.get(d, d) for d in s.depends_on],
            description=s.description,
        )
        merged.add_step(new_step)
    # Connect
    if connect_to and connect_to in {s.id for s in base.steps}:
        for s in merged.steps:
            if s.id.startswith("a_") and not s.depends_on:
                s.depends_on.append(connect_to)
    return merged


def estimate_plan_cost(plan: Plan) -> Dict[str, Any]:
    """Ước lượng chi phí plan (số tool calls, estimated tokens)."""
    tool_costs = {
        "search": 500,
        "read": 200,
        "write": 300,
        "calc": 50,
        "run_python": 1000,
        "now": 10,
        "list": 100,
    }
    total_tokens = 0
    tool_counts = defaultdict(int)
    for s in plan.steps:
        tool_counts[s.tool] += 1
        total_tokens += tool_costs.get(s.tool, 200)
    return {"tool_counts": dict(tool_counts), "estimated_tokens": total_tokens, "step_count": len(plan.steps)}


# ========== EXPORTS ==========
__all__ = [
    "Planner",
    "Plan",
    "merge_plans",
    "estimate_plan_cost",
]