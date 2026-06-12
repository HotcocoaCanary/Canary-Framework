"""框架日志工具。

提供框架内部日志记录功能。

Framework logging utilities.

Provides internal logging functionality for the framework.
"""

import logging
import sys
import threading

_logging_initialized = False
_logging_lock = threading.Lock()
_CF_LOGGER_NAME = "cf"


def ensure_logging(level: str = "INFO") -> None:
    """确保框架日志器已配置默认StreamHandler。

    仅执行一次（幂等）。如果用户已为cf日志器或root日志器
    手动配置了handler，则跳过。

    Args:
        level: 日志级别字符串（默认"INFO"）。

    Ensure the framework logger has a default StreamHandler.

    Executes only once (idempotent). Skips if the user has already
    manually configured a handler for the cf logger or root logger.

    Args:
        level: Log level string (default "INFO").
    """
    global _logging_initialized, _logging_lock
    if _logging_initialized:
        return
    with _logging_lock:
        if _logging_initialized:
            return

        cf_logger = logging.getLogger(_CF_LOGGER_NAME)

        if cf_logger.handlers:
            _logging_initialized = True
            return

        if logging.getLogger().handlers:
            _logging_initialized = True
            return

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(name)-20s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        cf_logger.addHandler(handler)
        cf_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        cf_logger.propagate = False
        _logging_initialized = True


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


__all__ = ["ensure_logging", "get_logger"]
