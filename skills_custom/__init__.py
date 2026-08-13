SKILLS_MANIFEST = {
    "ops_sync": {"kind": "active", "desc": "ops_sync", "module": "skills_custom.catalog.ops_sync", "run": "run"},
    "linux_filesystem": {"kind": "active", "desc": "linux fs", "module": "skills_custom.active.linux_filesystem", "run": "run"},
    "shell_command": {"kind": "active", "desc": "shell", "module": "skills_custom.active.shell_command", "run": "run"},
    "git_operations": {"kind": "active", "desc": "git", "module": "skills_custom.active.git_operations", "run": "run"},
    "text_processing": {"kind": "active", "desc": "text", "module": "skills_custom.active.text_processing", "run": "run"},
    "datetime_handling": {"kind": "active", "desc": "dt", "module": "skills_custom.active.datetime_handling", "run": "run"},
    "math_computation": {"kind": "active", "desc": "math", "module": "skills_custom.active.math_computation", "run": "run"},
    "json_processing": {"kind": "active", "desc": "json", "module": "skills_custom.active.json_processing", "run": "run"},
    "parallel_execution": {"kind": "active", "desc": "parallel", "module": "skills_custom.active.parallel_execution", "run": "run"},
    "process_management": {"kind": "active", "desc": "process", "module": "skills_custom.active.process_management", "run": "run"},
    "http_requests": {"kind": "active", "desc": "http", "module": "skills_custom.active.http_requests", "run": "run"},
    "web_extraction": {"kind": "active", "desc": "web extract", "module": "skills_custom.active.web_extraction", "run": "run"},
    "html_parsing": {"kind": "active", "desc": "html", "module": "skills_custom.active.html_parsing", "run": "run"},
    "deep_research": {"kind": "active", "desc": "research + store facts", "module": "skills_custom.active.deep_research", "run": "run"},
    "github_ops": {"kind": "active", "desc": "gh CLI GitHub ops", "module": "skills_custom.active.github_ops", "run": "run"},
    "email_ops": {"kind": "active", "desc": "email draft/triage", "module": "skills_custom.active.email_ops", "run": "run"},
    "browser_automation": {"kind": "active", "desc": "browser handoff + plans", "module": "skills_custom.active.browser_automation", "run": "run"},
    "knowledge_sync": {"kind": "active", "desc": "export/import knowledge", "module": "skills_custom.active.knowledge_sync", "run": "run"},
    "security_audit": {"kind": "active", "desc": "secret/input safety checks", "module": "skills_custom.active.security_audit", "run": "run"},
    "deepseek_philosophy": {"kind": "active", "desc": "3 Nos + AGI constraints", "module": "skills_custom.active.deepseek_philosophy", "run": "run"},
    "agi_roadmap": {"kind": "active", "desc": "6-step AGI roadmap tracker", "module": "skills_custom.active.agi_roadmap", "run": "run"},
    "income_roadmap": {"kind": "active", "desc": "legit income roadmap tracker", "module": "skills_custom.active.income_roadmap", "run": "run"},
    "income_opportunity_finder": {"kind": "active", "desc": "scan compliant income opportunities", "module": "skills_custom.active.income_opportunity_finder", "run": "run"},
    "income_focus": {"kind": "active", "desc": "choose and execute income focus with compliance", "module": "skills_custom.active.income_focus", "run": "run"},
    "web_scraping": {"kind": "docs", "desc": "scrape", "file": "skills_custom/catalog/web_scraping.md"},
    "web_search": {"kind": "docs", "desc": "search", "file": "skills_custom/catalog/web_search.md"},
    "web_fetch": {"kind": "docs", "desc": "fetch", "file": "skills_custom/catalog/web_fetch.md"},
    "task_delegation": {"kind": "docs", "desc": "delegate", "file": "skills_custom/catalog/task_delegation.md"},
    "python_execution": {"kind": "docs", "desc": "py exec", "file": "skills_custom/catalog/python_execution.md"},
    "cli_shell": {"kind": "docs", "desc": "cli", "file": "skills_custom/catalog/cli_shell.md"},
    "browser_control": {"kind": "docs", "desc": "browser", "file": "skills_custom/catalog/browser_control.md"},
    "proxy_networking": {"kind": "docs", "desc": "proxy", "file": "skills_custom/catalog/proxy_networking.md"},
}


def load_all(agi):
    from tools import TOOLS
    registered = []
    for name, meta in SKILLS_MANIFEST.items():
        if meta["kind"] != "active":
            continue
        module_fn = meta.get("module")
        if not module_fn:
            continue
        tool_name = f"custom_{name}"
        if tool_name in TOOLS:
            registered.append(name)
            continue
        try:
            import importlib
            mod = importlib.import_module(module_fn)
            if hasattr(mod, "run"):
                TOOLS[tool_name] = {"fn": mod.run, "needs_agent": True, "desc": meta["desc"]}
                registered.append(name)
        except Exception:
            pass
    return registered
