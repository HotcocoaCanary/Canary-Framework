"""Framework-wide logging utilities."""

from __future__ import annotations

import logging
import os
import re

_CF_NAMESPACE = "cf"
_cf_logger = logging.getLogger(_CF_NAMESPACE)

_SENSITIVE_RE = re.compile(
    r"(password|passwd|secret|token|key|api_key|auth|credential|private)",
    re.IGNORECASE,
)


def init_logging() -> None:
    level_name = os.environ.get("CF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    _cf_logger.setLevel(level)
    if _cf_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[CF] [%(levelname)-5s] [%(name)s] %(message)s")
    )
    _cf_logger.addHandler(handler)
    _cf_logger.propagate = False
    _cf_logger.debug("Logging initialised at level=%s", level_name)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{_CF_NAMESPACE}.{name}")


def sanitize_config_values(data: dict[str, object]) -> dict[str, object]:
    return {k: "***" if _SENSITIVE_RE.search(k) else v for k, v in data.items()}


__all__ = [
    "get_logger",
    "init_logging",
    "sanitize_config_values",
]
