---
name: clara-agi-code-fix-patterns
description: "Reusable code fix patterns discovered during CLARA-AGI v1.4 analysis session. Captures SQL injection fixes, process leak guards, config centralization, TF-IDF caching, web scraping resilience, AST validation for skills, and structured logging patterns."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-fixes, patterns, clara-agi, python, sqlite, web]
    related_skills: [systematic-debugging, test-driven-development, hermes-agent-skill-authoring]
---

# CLARA-AGI Code Fix Patterns

## Overview

Reusable fix patterns discovered during CLARA-AGI v1.4 codebase analysis and improvement session (2026-08-26). These patterns address common code quality and safety issues in local-first Python projects, particularly those with embedded SQLite, Ollama/MicroLLM backends, and dynamic skill generation.

Use this skill when: Applying CLARA-AGI fix patterns to CLARA-AGI or similar local-first Python projects.

---

## Fix Patterns

### Pattern 1: SQL Injection Prevention

**Trigger:** When writing SQL queries with user-controlled content in Python.

**Anti-pattern:** f-string interpolation of query parts:
```python
self.conn.execute(f"UPDATE goals SET {', '.join(sets)} WHERE id=?", vals)
```

**Fix:** Parameterized queries with fixed column names only:
```python
sets, vals = [], []
if status:
    sets.append("status=?")
    vals.append(status)
if progress:
    sets.append("progress=?")
    vals.append(progress)
if priority is not None:
    sets.append("priority=?")
    vals.append(priority)
if not sets:
    return
# Build query safely - sets contains only fixed column names
query = "UPDATE goals SET " + ", ".join(sets) + " WHERE id=?"
vals.append(gid)
self.conn.execute(query, vals)
self.conn.commit()
```

**Key principle:** Never interpolate user-controlled content into SQL. Only fixed, known column names may be joined into the query string.

---

### Pattern 2: Process Leak Guard

**Trigger:** Using `multiprocessing.Process` for sandboxed code execution.

**Anti-pattern:** No guaranteed cleanup on timeout:
```python
p = mp.Process(target=_run_code_proc, args=(code, q), daemon=True)
p.start()
p.join(timeout)
if p.is_alive():
    p.terminate()
    p.join(1)
    return f"⏱️ Code chạy quá {timeout}s, đã dừng."
```

**Fix:** Always use `try/finally` with guaranteed join:
```python
q = mp.Queue()
p = mp.Process(target=_run_code_proc, args=(code, q), daemon=True)
try:
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        return f"⏱️ Code chạy quá {timeout}s, đã dừng."
    if q.empty():
        return "❌ Không có kết quả trả về."
    status, val = q.get()
    return val if status == "ok" else val
finally:
    # Ensure process is always cleaned up
    if p.is_alive():
        p.terminate()
        p.join(1)
```

**Key principle:** `finally` block guarantees process cleanup regardless of code path taken.

---

### Pattern 3: Config Centralization

**Trigger:** Multiple `os.environ.get()` calls with fallback values scattered across code.

**Anti-pattern:**
```python
OLLAMA_URL = os.environ.get("CLARA_OLLAMA_URL", "http://localhost:11434")
DEFAULT_OLLAMA = "qwen2.5:1.5b"
CANDIDATE_MODELS = [...]
```

**Fix:** Centralized `config.yaml` + `config.py` loader:

**config.yaml:**
```yaml
llm:
  backend: "ollama"
  ollama_url: "http://localhost:11434"
  default_model: "qwen2.5:1.5b"
  candidate_models: [...]
  temperature: 0.5
  num_predict: 400
  request_timeout: 120
```

**config.py:**
```python
class Config:
    _instance = None
    _config = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self):
        # 1. Default config embedded
        self._config = self._default_config()
        # 2. Load from config.yaml if exists
        config_path = Path(__file__).parent / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                self._deep_merge(self._config, file_config)
            except Exception as e:
                print(f"[Config] Warning: Failed to load config.yaml: {e}")
        # 3. Override with environment variables
        self._apply_env_overrides()
    
    def get(self, *keys, default=None):
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def section(self, name):
        return self._config.get(name, {}).copy()
```

**Key principle:** All configurable parameters in one file; environment variables override defaults; typed accessors prevent env-parse errors.

---

### Pattern 4: TF-IDF Caching with Graceful Fallback

**Trigger:** Semantic recall/similarity search over growing fact base.

**Anti-pattern:** `fit_transform` toàn bộ corpus mỗi lần recall → O(n²) chậm:
```python
vectorizer = TfidfVectorizer(...)
tfidf = vectorizer.fit_transform(all_facts)  # SLOW for >500 facts
```

**Fix:** Lazy rebuild only when dirty; sklearn absent → fallback:
```python
def _rebuild_tfidf_cache(self):
    """Rebuild TF-IDF vectorizer and matrix from current semantics."""
    if not _HAS_SKLEARN:
        return
    c = self.conn.cursor()
    rows = c.execute(
        "SELECT topic, fact FROM semantics WHERE confidence>=? ORDER BY last_access DESC LIMIT ?",
        (self._min_confidence, self._max_semantics_recall)
    ).fetchall()
    if not rows:
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._tfidf_facts = []
        return
    self._tfidf_facts = [(r["topic"], r["fact"]) for r in rows]
    corpus = [topic + " " + fact for topic, fact in self._tfidf_facts]
    if len(corpus) > 5000:
        from sklearn.feature_extraction.text import HashingVectorizer
        self._tfidf_vectorizer = HashingVectorizer(n_features=2**16, alternate_sign=False, norm='l2', lowercase=True, ngram_range=(1, 2))
        self._tfidf_matrix = self._tfidf_vectorizer.transform(corpus)
    else:
        self._tfidf_vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=10000, min_df=1, max_df=0.95)
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(corpus)
    self._tfidf_dirty = False

def _get_tfidf_scores(self, query: str):
    if self._tfidf_dirty or self._tfidf_vectorizer is None or self._tfidf_matrix is None:
        self._rebuild_tfidf_cache()
    if self._tfidf_vectorizer is None or self._tfidf_matrix is None:
        return None
    try:
        q_vec = self._tfidf_vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._tfidf_matrix).flatten()
        return scores
    except Exception:
        return None
```

**Key principle:** Cache vectorizer + matrix; rebuild only when facts change (`_tfidf_dirty`); `HashingVectorizer` for large corpuses; graceful sklearn-absent fallback to keyword/embedding scoring.

---

### Pattern 5: BeautifulSoup Web Parse + Retry/Backoff

**Trigger:** Parsing HTML from web search results or page fetch.

**Anti-pattern:** Regex-only DDG HTML parse → breaks when layout changes; no retry:
```python
blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?', html, re.S)
```

**Fix:** BeautifulSoup with multiple selectors + exponential backoff:
```python
_web_cfg = get_config("web")
USER_AGENT = _web_cfg.get("user_agent", "Mozilla/5.0...")
FETCH_TIMEOUT = _web_cfg.get("fetch_timeout", 15)
RETRY_ATTEMPTS = _web_cfg.get("retry_attempts", 3)
RETRY_BACKOFF_BASE = _web_cfg.get("retry_backoff_base", 2.0)
RETRY_MAX_BACKOFF = _web_cfg.get("retry_max_backoff", 30.0)
RATE_LIMIT_DELAY = _web_cfg.get("rate_limit_delay", 1.0)

_last_request_time = 0.0

def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()

def _request_with_retry(url: str, timeout: int = FETCH_TIMEOUT) -> str:
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            _rate_limit()
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < RETRY_ATTEMPTS - 1:
                backoff = min(RETRY_BACKOFF_BASE ** attempt, RETRY_MAX_BACKOFF)
                time.sleep(backoff)
    raise Exception(f"Request failed after {RETRY_ATTEMPTS} attempts: {last_error}")
```

**Key principle:** BeautifulSoup with BS4 preference + regex fallback; retry with exponential backoff; rate-limit between requests; user-agent rotation.

---

### Pattern 6: AST Validation for Skill Code

**Trigger:** Validating dynamically-generated Python skill code before registration/execution.

**Anti-pattern:** String-pattern blacklist → easily bypassed:
```python
BLOCKED_PATTERNS = ["os.system", "subprocess", "eval(", ...]
def _safe_code(code: str) -> bool:
    c = code.lower()
    return not any(p in c for p in BLOCKED_PATTERNS)
```

**Fix:** AST tree walk — block imports from non-safe modules, blocked attributes, blocked names:
```python
_SAFE_IMPORTS = {"math", "random", "statistics", "datetime", "collections",
                 "itertools", "functools", "re", "json", "string", "time",
                 "pathlib", "os.path", "urllib.parse", "urllib.request"}

_BLOCKED_ATTR = {"__import__", "__subclasses__", "__class__", "__bases__",
                 "__mro__", "__globals__", "__code__", "__func__", "__self__",
                 "eval", "exec", "compile", "open", "input", "breakpoint",
                 "__builtins__", "globals", "locals", "getattr"}

_BLOCKED_NAMES = {"open", "eval", "exec", "compile", "__import__",
                  "globals", "locals", "breakpoint", "input", "exit", "quit"}


def _validate_skill_ast(code: str) -> bool:
    """Validate skill code AST for safety."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] not in _SAFE_IMPORTS:
                        return False
                else:
                    for n in node.names:
                        if n.name.split(".")[0] not in _SAFE_IMPORTS:
                            return False
            if isinstance(node, ast.Attribute):
                if node.attr in _BLOCKED_ATTR:
                    return False
            if isinstance(node, ast.Name):
                if node.id in _BLOCKED_NAMES:
                    return False
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_NAMES:
                    return False
                if isinstance(node.func, ast.Attribute) and node.func.attr in _BLOCKED_ATTR:
                    return False
        return True
    except SyntaxError:
        return False
```

**Key principle:** AST structure validation, not text-string matching; blocks `__import__`, `eval`, `exec`, `compile`, `open`, `input`, `breakpoint`, `getattr`, `globals`, `locals` at all levels; safe import whitelist.

---

### Pattern 7: Structured Logging

**Trigger:** Any production Python code needing diagnostics.

**Anti-pattern:** `print()` statements everywhere → no rotation, no levels, hard to correlate.

**Fix:** `logging_utils.py` with JSON/text formatters, rotation, convenience functions:

```python
import logging
import logging.handlers
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from config import get_config


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "pathname", "process", "processName",
                          "relativeCreated", "thread", "threadName", "exc_info",
                          "exc_text", "stack_info", "getMessage"):
                log_data[key] = value
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )


def setup_logging(name: str = "clara") -> logging.Logger:
    log_cfg = get_config("logging")
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_cfg.get("level", "INFO").upper()))
    logger.handlers.clear()
    
    if log_cfg.get("console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        if log_cfg.get("format") == "json":
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(TextFormatter())
        logger.addHandler(console_handler)
    
    log_file = log_cfg.get("file")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=log_cfg.get("max_bytes", 10485760),
            backupCount=log_cfg.get("backup_count", 5),
            encoding="utf-8"
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    logger.propagate = False
    return logger


def log_info(logger: logging.Logger, message: str, **extra):
    logger.info(message, extra=extra if extra else None)

def log_warning(logger: logging.Logger, message: str, **extra):
    logger.warning(message, extra=extra if extra else None)

def log_error(logger: logging.Logger, message: str, **extra):
    logger.error(message, extra=extra if extra else None)

def log_debug(logger: logging.Logger, message: str, **extra):
    logger.debug(message, extra=extra if extra else None)

def log_exception(logger: logging.Logger, message: str, **extra):
    logger.exception(message, extra=extra if extra else None)
```

**Key principle:** JSON formatter with timestamp, level, logger, module, function, line; text formatter for console; `RotatingFileHandler` with maxBytes/backupCount; convenience `log_*()` functions with `**extra` passthrough.

---

## Support Files (references/)

- `references/sql-injection-patterns.md` — Detailed SQL anti-patterns and parameterized query examples
- `references/tfidf-cache-strategy.md` — TF-IDF caching strategy with sklearn fallback details
- `references/web-scraping-resilience.md` — BeautifulSoup + retry patterns, rate limits, user-agent rotation

## Version

v1.0.0 — Initial pattern capture from CLARA-AGI v1.4 analysis session (2026-08-26)

## Hermes Integration

To use these patterns within Hermes:

1. **Load the skill:** `hermes skill load clara-agi-code-fix-patterns`
2. **Reference patterns:** The skill includes trigger conditions and anti-pattern/fix pairs
3. **Adapt to your project:** Copy the relevant pattern section into your codebase
4. **Extend:** Add new patterns as discoveries are made; update `references/` support files

---

## Relation to CLARA-AGI Fixes

These patterns codify the fixes applied during the CLARA-AGI v1.4 analysis session:

| Pattern | CLARA-AGI File Fixed |
|---------|---------------------|
| SQL Injection Prevention | `memory.py:update_goal()` |
| Process Leak Guard | `tools.py:tool_run_python()` |
| Config Centralization | `config.yaml`, `config.py` (new) |
| TF-IDF Caching | `memory.py:recall_semantics()` |
| Web Scraping Resilience | `web_tools.py` (complete rewrite) |
| AST Validation | `self_improve.py:propose_skill()` |
| Structured Logging | `logging_utils.py` (new), integrated into `main.py`, `agent.py` |

---

## References

- CLARA-AGI GitHub: https://github.com/zeusyxa-tech/CLARA-AGI
- Hermes Agent Docs: https://hermes-agent.nousresearch.com/docs