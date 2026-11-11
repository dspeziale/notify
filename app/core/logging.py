"""Structured logging with automated sensitive data redaction."""

import json
import logging
import re
import sys
from typing import Any

# Patterns to mask in logs
SENSITIVE_PATTERNS = [
    (re.compile(r'(?i)(token["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(api[_-]?key["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(secret["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(password["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(refresh_token["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(access_token["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(authorization["\']?\s*[:=]\s*["\']Bearer\s+)([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(x-api-key["\']?\s*[:=]\s*["\'])([^"\']+)'), r"\1[REDACTED]"),
    (re.compile(r'(?i)(bot[0-9]+:[a-zA-Z0-9_-]+)'), r"[REDACTED_TELEGRAM_TOKEN]"),
    (re.compile(r'(?i)(ng_live_[a-zA-Z0-9_-]+)'), r"[REDACTED_API_KEY]"),
]


def redact_sensitive_text(text: str) -> str:
    """Redacts any sensitive tokens, passwords, and keys from a string."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SensitiveDataFilter(logging.Filter):
    """Logging filter that cleans sensitive patterns from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                cleaned_args = {}
                for k, v in record.args.items():
                    if any(secret_term in str(k).lower() for secret_term in ["token", "secret", "password", "key"]):
                        cleaned_args[k] = "[REDACTED]"
                    elif isinstance(v, str):
                        cleaned_args[k] = redact_sensitive_text(v)
                    else:
                        cleaned_args[k] = v
                record.args = cleaned_args
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "application_id"):
            log_data["application_id"] = str(record.application_id)
        return json.dumps(log_data)


def setup_logging(debug: bool = False) -> None:
    """Configures the root and application loggers."""
    log_level = logging.DEBUG if debug else logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.addFilter(SensitiveDataFilter())

    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress verbose noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
