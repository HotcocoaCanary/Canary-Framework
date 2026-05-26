"""Shared enumerations used across the framework.

设计选择 (Design choice): 使用 ``StrEnum`` 而非普通字符串
    过去框架用字符串 ``"on_init"`` / ``"on_start"`` / ``"on_end"`` 到处传播，
    导致 IDE 无法自动补全，重构时容易遗漏，拼写错误只能在运行时发现。
    ``StrEnum`` 继承自 ``str``，既能用于字符串比较（``== "on_init"``），
    也有独立的 namespace 防止魔法字符串散落。

    Before: string literals scattered across ``canary.py`` and ``lifecycle.py``.
    After:  single source of truth in :class:`LifecycleHook`.
"""

from __future__ import annotations

from enum import StrEnum


class LifecycleHook(StrEnum):
    """Enumeration of valid lifecycle hook names.

    框架内部通过此枚举查找钩子，替代原来的字符串匹配。
    每个枚举值与装饰器方法上设置的私有标记属性一一对应。

    Used internally by the conductor to look up hooks on service/module
    instances.  Each member corresponds to a private marker attribute set
    by ``@on_init`` / ``@on_start`` / ``@on_end``.
    """

    INIT = "on_init"
    """Called after DI and config loading.  No arguments — dependencies
    and config are injected as instance attributes before the hook runs.

    初始化钩子：此时依赖和配置已通过 DI 注入为实例属性。无参数。"""

    START = "on_start"
    """Called in topological order during application start.  No arguments.

    启动钩子：按拓扑序依次调用，无参数。适合启动连接池、监听端口等."""

    END = "on_end"
    """Called in reverse topological order during application stop.  No arguments.

    停止钩子：按逆拓扑序依次调用，无参数。依赖方先停止，被依赖方后停止。
    适合关闭连接、刷新缓冲区等操作."""
