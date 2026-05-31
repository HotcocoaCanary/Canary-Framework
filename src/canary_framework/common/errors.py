"""Framework-specific exception classes.

所有框架异常均继承自CanaryFrameworkError基类，
调用者可以捕获单一类型来处理所有框架错误。

All framework errors inherit from CanaryFrameworkError, so callers can
catch a single type to handle any framework error.
"""

from __future__ import annotations


class CanaryFrameworkError(Exception):
    """Canary Framework的基础异常类。

    Base exception class for all Canary Framework errors.
    """


class ConfigurationError(CanaryFrameworkError):
    """配置加载或验证失败时抛出。

    Raised when configuration loading or validation fails.
    """


class ServiceNotFoundError(CanaryFrameworkError):
    """请求的服务或模块无法定位时抛出。

    Raised when a requested service or module cannot be located.
    """


class CircularDependencyError(CanaryFrameworkError):
    """拓扑排序检测到循环依赖时抛出。

    Raised when the topological sort detects a cycle.
    """


class DependencyInjectionError(CanaryFrameworkError):
    """依赖注入在运行时失败时抛出。

    Raised when dependency injection fails at runtime.
    """


class LifecycleHookError(CanaryFrameworkError):
    """运行时钩子抛出未处理异常时抛出。

    Raised when a runtime hook raises an unhandled exception.
    """


__all__ = [
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHookError",
    "ServiceNotFoundError",
]