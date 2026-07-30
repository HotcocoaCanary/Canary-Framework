"""Framework logging utilities."""

import logging
import sys
import threading

_logging_initialized = False
_logging_lock = threading.Lock()
_CF_LOGGER_NAME = "cf"


def ensure_logging(level: str = "INFO") -> None:
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
    return logging.getLogger(f"cf.{name}")


__all__ = ["ensure_logging", "get_logger"]
