"""框架日志工具。

提供日志初始化和敏感信息脱敏功能。

Framework logging utilities.

Provides logging initialization and sensitive data redaction.
"""

import logging
import os
from typing import Any


def init_logging(level: int | None = None) -> None:
    """初始化框架日志系统。

    设置Canary Framework的日志配置，包括格式化和级别设置。
    如果未指定级别，将从环境变量CF_LOG_LEVEL读取。

    Args:
        level: 日志级别（可选）。

    Initialize the framework logging system.

    Configures logging for Canary Framework with proper formatting and level.
    If no level is specified, reads from CF_LOG_LEVEL environment variable.

    Args:
        level: Log level (optional).
    """
    if level is None:
        level_name = os.environ.get("CF_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("cf")
    logger.setLevel(level)

    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """获取框架子日志器。

    创建并返回以"cf."为前缀的日志器。

    Args:
        name: 子日志器名称。

    Returns:
        日志器实例。

    Get a framework sub-logger.

    Creates and returns a logger with "cf." prefix.

    Args:
        name: Sub-logger name.

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"cf.{name}")


def sanitize_config_values(config: dict[str, Any]) -> dict[str, Any]:
    """脱敏配置字典中的敏感信息。

    将密码、密钥、token等敏感字段的值替换为***。

    Args:
        config: 配置字典。

    Returns:
        脱敏后的配置字典。

    Sanitize sensitive information in config dictionary.

    Replaces values of sensitive fields like passwords, keys, and tokens with ***.

    Args:
        config: Configuration dictionary.

    Returns:
        Sanitized configuration dictionary.
    """
    sensitive_keys = {"password", "secret", "token", "key", "api_key", "auth_token"}
    result = {}
    for key, value in config.items():
        lower_key = key.lower()
        if any(sensitive in lower_key for sensitive in sensitive_keys):
            result[key] = "***"
        else:
            result[key] = value
    return result


__all__ = ["get_logger", "init_logging", "sanitize_config_values"]