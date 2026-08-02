# Python Execution Reference (docs)
Sandbox pattern trong CLARA `tool_run_python`.
- Parse AST trước khi exec, kiểm tra import whitelist, block attribute nguy hiểm, block eval/exec/__import__/open/input/breakpoint.
- Builtins: allowlist nhỏ; block __builtins__ injection.
- Resource limit: run trong Process riêng, join(timeout=8s), terminate nếu quá hạn.
- Output capture: redirect_stdout/stderr -> StringIO; fallback result variable.
- No side effects: chỉ cho workspace, chỉ thao tác trong memory/object.
- State: process mới không chia sẻ state về parent; không được truy cập DB/mem trực tiếp từ exec.
- Memory: auto-dismiss process objects, drain queue when done.
