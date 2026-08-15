"""Common — shared types and errors, with no framework logic.

共享层：仅含类型与异常，不掺入框架逻辑。核心包与扩展包（web / agent / …）
都从这里继承基类，保证跨包的类型与错误可统一校验、统一捕获。
"""

from canary_framework.common.error import (
    CanaryError,
    CircularDependencyError,
    LifecycleError,
)
from canary_framework.common.type import LifecycleState, State

__all__ = [
    "CanaryError",
    "CircularDependencyError",
    "LifecycleError",
    "LifecycleState",
    "State",
]
