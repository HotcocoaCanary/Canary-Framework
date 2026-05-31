"""框架日志工具。

提供框架内部日志记录功能。

Framework logging utilities.

Provides internal logging functionality for the framework.
"""

import logging


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


__all__ = ["get_logger"]
