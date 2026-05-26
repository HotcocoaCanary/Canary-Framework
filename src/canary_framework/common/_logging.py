"""Framework-wide logging utilities.

设计思路 (Design rationale):
    为什么 extract 到 common 而不是放在 core?
    （Why extract to common instead of core?）

    日志系统被 conductor、algorithms、web 等多个模块共同使用，
    放在 common 中避免了 core→web 的循环依赖风险，也符合"共用基础设施"的定位。

    命名约定 (Naming):
        ``_logging.py`` 以下划线开头，表明它是框架内部模块。
        The leading underscore signals this is an internal module,
        not part of the public API surface.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

# ============================================================================
# 日志命名空间 (Logger namespace)
# ============================================================================

_CF_NAMESPACE = "cf"
"""Root namespace for all framework loggers.  All child loggers are
created as ``cf.<name>`` (e.g. ``cf.engine``, ``cf.di``, ``cf.web``)."""

# ============================================================================
# 最高层 logger (Root framework logger)
# ============================================================================

_cf_logger = logging.getLogger(_CF_NAMESPACE)

# ============================================================================
# 敏感字段正则 (Sensitive field regex — used for config sanitization)
# ============================================================================

_SENSITIVE_RE = re.compile(
    r"(password|passwd|secret|token|key|api_key|auth|credential|private)",
    re.IGNORECASE,
)
"""不区分大小写匹配包含密码/密钥/Token 等的字段名。
Case-insensitive match for field names containing sensitive keywords."""


# ============================================================================
# 公共工具函数 (Public utility functions)
# ============================================================================


def init_logging() -> None:
    """Initialize the framework root logger (idempotent).

    幂等初始化：多次调用不会重复添加 handler。
    从 ``CF_LOG_LEVEL`` 环境变量读取日志级别（默认 INFO）。
    ``propagate=False`` 防止日志传播到 root logger。

    Idempotent: multiple calls won't add duplicate handlers.
    Reads ``CF_LOG_LEVEL`` env var (default ``INFO``).
    """
    level_name = os.environ.get("CF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    _cf_logger.setLevel(level)

    # 幂等检查：已有 handler 则跳过
    if _cf_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[CF] [%(levelname)-5s] [%(name)s] %(message)s"))
    _cf_logger.addHandler(handler)
    _cf_logger.propagate = False
    _cf_logger.debug("Logging initialised at level=%s", level_name)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``cf`` namespace.

    返回 ``cf.<name>`` 子 logger，如 ``cf.engine``、``cf.di``。"""
    return logging.getLogger(f"{_CF_NAMESPACE}.{name}")


def sanitize_config_values(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive values replaced by ``'***'``.

    返回脱敏后的配置字典副本，敏感字段值替换为 ``***``。
    不会修改原始字典。

    敏感字段匹配规则：字段名（忽略大小写）包含
    password、passwd、secret、token、key、api_key、auth、credential、private。
    """
    return {k: "***" if _SENSITIVE_RE.search(k) else v for k, v in data.items()}
