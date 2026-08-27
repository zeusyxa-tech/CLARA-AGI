"""
CLARA-AGI - Structured Logging Module
Cung cấp logging có cấu trúc (JSON) với rotation, level, console output.
"""
import logging
import logging.handlers
import json
import sys
import os
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
        # Add extra fields if present (via extra= parameter)
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "name", "pathname", "process", "processName",
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
    """
    Setup logging from config.
    Returns configured logger.
    """
    log_cfg = get_config("logging")
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_cfg.get("level", "INFO").upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if log_cfg.get("console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        if log_cfg.get("format") == "json":
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(TextFormatter())
        logger.addHandler(console_handler)
    
    # File handler with rotation
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
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str = "clara") -> logging.Logger:
    """Get logger instance (creates if not exists)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger


# Convenience functions
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