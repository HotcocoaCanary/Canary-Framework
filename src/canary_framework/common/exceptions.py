"""Framework-specific exceptions.

设计思路 (Design rationale):
    所有异常继承自同一个基类 ``CanaryFrameworkError``，用户只需捕获一个异常类型
    即可兜底所有框架错误，而不会误吞系统级异常（如 ``MemoryError``）。

    All exceptions inherit from :class:`CanaryFrameworkError`, so callers can
    catch a single type to handle any framework error while letting
    system-level exceptions propagate.

Hierarchy::

    CanaryFrameworkError
    ├── ConfigurationError
    ├── ServiceNotFoundError
    ├── CircularDependencyError
    ├── DependencyInjectionError
    └── LifecycleHookError
"""

from __future__ import annotations


class CanaryFrameworkError(Exception):
    """Base class for all Canary Framework exceptions.

    框架所有异常的基类。用户只需 ``except CanaryFrameworkError`` 即可兜底
    所有框架层错误，同时让系统级异常（如 ``KeyboardInterrupt``）正常传递。

    Catch this to handle any framework-originated error while allowing
    system-level and third-party exceptions to pass through.
    """


class ConfigurationError(CanaryFrameworkError):
    """Raised when configuration loading or validation fails.

    触发场景 (When raised):
        - ``ctx.config_as()`` 在整个 parent 链上找不到配置实例
        - ``@config`` 类缺少必要的 pydantic 字段声明
        - pydantic 在构造时校验失败
    """


class ServiceNotFoundError(CanaryFrameworkError):
    """Raised when a requested service or module cannot be located.

    触发场景 (When raised):
        - ``Registry.get_by_name(name)`` 传入未注册的名称
        - ``Context.resolve(cls)`` 在当前模块及其祖先模块中找不到该服务
        - ``deps=[]`` 中声明了未被 ``@service`` 或 ``@module`` 装饰的类
    """


class CircularDependencyError(CanaryFrameworkError):
    """Raised when the topological sort detects a cycle.

    触发场景 (When raised):
        - 服务 A 依赖 B，B 依赖 A（直接循环）
        - 服务自身依赖自身（自循环）
        - 多服务形成间接循环依赖链

    The error message includes the names of the services that form the cycle.
    """


class DependencyInjectionError(CanaryFrameworkError):
    """Raised when dependency injection fails at runtime.

    触发场景 (When raised):
        - ``inject_deps()`` 时目标依赖的 ``instance`` 为 ``None``（尚未初始化）
        - 通常在启动顺序错误或手动操作 Registry 时发生
    """


class LifecycleHookError(CanaryFrameworkError):
    """Raised when a lifecycle hook raises an unhandled exception.

    将钩子内部的异常包装为此类型，让调用方可以区分：
    - 钩子自己的业务逻辑错误
    - 框架本身的 bug

    Wraps the hook's original exception so callers can distinguish between
    a hook's business-logic failure and a framework bug.
    """
