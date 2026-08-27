"""
CLARA-AGI Configuration Loader
Tải config từ config.yaml, fallback về environment variables, cuối cùng là defaults.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        # 1. Default config (embedded)
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

    def _default_config(self) -> Dict[str, Any]:
        return {
            "llm": {
                "backend": "ollama",
                "ollama_url": "http://localhost:11434",
                "default_model": "qwen2.5:1.5b",
                "candidate_models": [
                    "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b",
                    "phi3.5:mini", "gemma2:2b", "tinyllama",
                    "llama3.2:1b", "llama3.2:3b", "mistral:7b",
                ],
                "temperature": 0.5,
                "num_predict": 400,
                "request_timeout": 120,
            },
            "embeddings": {
                "model": "nomic-embed-text",
                "ollama_url": "http://localhost:11434",
                "cache_enabled": True,
            },
            "memory": {
                "db_dir": "data",
                "db_name": "clara.db",
                "embeddings_db": "embeddings.db",
                "workspace_dir": "workspace",
                "max_semantics_recall": 500,
                "min_confidence": 0.2,
            },
            "tools": {
                "python_timeout": 8,
                "python_max_output_chars": 4000,
                "calc_max_expression_length": 200,
                "file_max_read_chars": 4000,
            },
            "web": {
                "search_engine": "duckduckgo",
                "max_results": 5,
                "fetch_timeout": 15,
                "fetch_max_chars": 4000,
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "retry_attempts": 3,
                "retry_backoff_base": 2.0,
                "retry_max_backoff": 30.0,
                "rate_limit_delay": 1.0,
            },
            "autolearner": {
                "enabled": False,
                "interval_seconds": 25,
                "max_steps": None,
                "verbose": True,
                "activities": {
                    "consolidate": 0.20,
                    "reflect_old": 0.15,
                    "self_qa": 0.15,
                    "dream": 0.10,
                    "goal_check": 0.10,
                    "curiosity": 0.10,
                    "lesson_delivery": 0.20,
                },
            },
            "scheduler": {
                "enabled": False,
                "interval_seconds": 120,
                "daily_quiz_count": 2,
                "weekly_review_day": 6,
            },
            "self_improve": {
                "max_pages_research": 3,
                "max_facts_per_page": 5,
                "min_confidence": 0.5,
                "dedup_threshold": 0.85,
            },
            "compliance": {
                "owner_policy_path": "owner_policy.json",
                "jurisdiction_priority": "Vietnam",
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "file": "logs/clara.log",
                "max_bytes": 10485760,
                "backup_count": 5,
                "console": True,
            },
            "agent": {
                "working_memory_max_turns": 20,
                "reflection_threshold": 5,
                "rewrite_max_sentences": 4,
                "default_language": "vi",
            },
        }

    def _deep_merge(self, base: Dict, override: Dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _apply_env_overrides(self):
        """Override config with environment variables"""
        env_mapping = {
            "CLARA_OLLAMA_URL": ("llm", "ollama_url"),
            "CLARA_MODEL": ("llm", "default_model"),
            "CLARA_DB_DIR": ("memory", "db_dir"),
            "CLARA_DB_PATH": ("memory", "db_name"),  # note: this overrides full path
            "OPENAI_API_BASE": ("llm", "ollama_url"),  # compat
            "OPENAI_API_KEY": ("llm", "api_key"),
            "CLARA_LOG_LEVEL": ("logging", "level"),
            "CLARA_LOG_FILE": ("logging", "file"),
        }
        for env_var, (section, key) in env_mapping.items():
            value = os.environ.get(env_var)
            if value:
                if section not in self._config:
                    self._config[section] = {}
                # Type conversion
                if key in ("request_timeout", "python_timeout", "fetch_timeout", "interval_seconds", "max_steps"):
                    value = int(value)
                elif key in ("temperature", "min_confidence", "dedup_threshold"):
                    value = float(value)
                elif key in ("enabled", "cache_enabled", "console"):
                    value = value.lower() in ("true", "1", "yes")
                self._config[section][key] = value

    def get(self, *keys: str, default: Any = None) -> Any:
        """Lấy config theo nested keys: config.get('llm', 'temperature')"""
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def section(self, name: str) -> Dict[str, Any]:
        """Lấy toàn bộ section"""
        return self._config.get(name, {}).copy()

    @property
    def all(self) -> Dict[str, Any]:
        return self._config.copy()


# Singleton instance
config = Config()


# Convenience functions
def get_config(*keys, default=None):
    return config.get(*keys, default=default)


def get_section(name):
    return config.section(name)