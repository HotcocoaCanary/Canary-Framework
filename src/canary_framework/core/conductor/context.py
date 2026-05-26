"""Unified runtime context — the service/module's connection to the framework.

设计思路 (Design rationale):
    为什么需要 Context？
    （Why do we need Context?）

    最初的设计中，服务的 ``on_init`` 直接接收 ``registry`` 和 ``config``
    两个参数。这导致两个问题：
    1. 参数爆炸：每增加一个框架能力就要加一个参数
    2. 依赖方向错误：服务需要知道 Registry 的内部结构

    Context 将所有框架能力封装在一个对象中，通过 parent 链向上委托查找。
    服务只依赖一个 Context，框架可以自由扩展 Context 的方法而不破坏 API。

    Parent 链 (The parent chain):
        每个 Context 都有一个 ``_parent`` 指向所属模块的 Context。
        当当前节点查找不到配置时，自动沿链上溯。
        这是一种「责任链」模式的简化实现：每个节点要么自己处理请求，
        要么委托给父节点。

    类型安全访问 (Type-safe access):
        ``get_config(Type)`` 和 ``get_service(Type)`` 通过泛型参数让 IDE
        能推断返回值的类型，在编译时即可发现类型错误，无需等到运行时。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from canary_framework.common.exceptions import (
    ConfigurationError,
    ServiceNotFoundError,
)

if TYPE_CHECKING:
    from canary_framework.common._types import ServiceEntry
    from canary_framework.core.container.registry import Registry

_ConfigT = TypeVar("_ConfigT")
"""Config type for :meth:`get_config`."""

_ServiceT = TypeVar("_ServiceT")
"""Service type for :meth:`get_service`."""


class Context:
    """Unified runtime context for a service or module instance.

    统一运行时上下文。通过 parent 链向上委托配置和依赖解析。

    提供给 ``@on_init`` 钩子。"""

    __slots__ = ("_entry", "_parent", "_registry")

    def __init__(
        self,
        entry: ServiceEntry,
        parent: Context | None,
        registry: Registry,
    ) -> None:
        self._entry = entry
        self._parent = parent
        self._registry = registry

    # ==================================================================
    # 类型安全的访问器 (Typed accessors)
    # ==================================================================

    def get_config(self, cls: type[_ConfigT]) -> _ConfigT:
        """Return the config instance with full type safety.

        返回类型安全的配置实例。

        沿 parent 链向上查找第一个 ``config_instance`` 非 None 的节点。
        时间复杂度 O(d)，d 为模块树深度。

        Args:
            cls: 期望的 ``@config`` 装饰类，仅用于静态类型推断，
                 实际运行时不校验类型。

        Returns:
            配置实例，类型为 *cls*。

        Raises:
            ConfigurationError: 整个 parent 链上都未找到配置实例。

        Example::

            @on_init
            def init(self, ctx: Context) -> None:
                cfg = ctx.get_config(AppConfig)
                print(cfg.host)  # IDE 能推断 host 的类型为 str
        """
        cur: Context | None = self
        while cur is not None:
            inst = cur._entry.config_instance
            if inst is not None:
                return inst  # type: ignore[return-value]
            cur = cur._parent
        raise ConfigurationError(
            "No config instance bound to this context chain. "
            "Ensure the root module declares a @config class."
        )

    def get_service(self, cls: type[_ServiceT]) -> _ServiceT:
        """Return the runtime instance of *cls* with full type safety.

        在模块树中查找并返回指定服务的运行时实例。

        查找策略:
            1. 首先检查当前 Context 绑定的 service 是否为 *cls*
            2. 若不是，沿 parent 链向上，在每个模块的 ``sub_services``
               中按 ``__cf_name__`` 进行匹配
            3. 找到则通过 Registry 返回运行时实例
            4. 遍历完整个 parent 链仍未找到 → 抛出 ServiceNotFoundError

        Args:
            cls: 被 ``@service`` 或 ``@module`` 装饰的类。

        Returns:
            运行时实例，类型为 *cls*。

        Raises:
            ServiceNotFoundError: 当前模块及其所有祖先模块中均未找到。

        Example::

            @on_init
            def init(self, ctx: Context) -> None:
                db = ctx.get_service(DBService)
                db.query(...)
        """
        name = getattr(cls, "__cf_name__", cls.__name__)

        # 先检查当前 entry 本身
        if self._entry.cls is cls or getattr(self._entry.cls, "__cf_name__", "") == name:
            return self._entry.instance  # type: ignore[return-value]

        # 沿 parent 链向上搜索
        cur: Context | None = self
        while cur is not None:
            entry = cur._entry
            if entry.is_module:
                for sub_cls in entry.sub_services:
                    if getattr(sub_cls, "__cf_name__", "") == name:
                        return self._registry.get_instance(sub_cls)  # type: ignore[return-value]
            cur = cur._parent

        raise ServiceNotFoundError(
            f"Service '{name}' not found in this module or any parent module. "
            f"Ensure it is declared in the 'services' list of a parent @module."
        )
