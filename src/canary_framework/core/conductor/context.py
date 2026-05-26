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
        ``get_config(Type)`` 通过泛型参数让 IDE 能推断返回值的类型，
        在编译时即可发现类型错误，无需等到运行时。
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

_C = TypeVar("_C")
"""Config type for :meth:`get_config`."""

_S = TypeVar("_S")
"""Service type for :meth:`get_service` and :meth:`resolve`."""


class Context:
    """Unified runtime context for a service or module instance.

    统一运行时上下文。通过 parent 链向上委托配置和依赖解析。

    提供给 ``@on_init`` 钩子和 ``@router`` 构造函数。"""

    __slots__ = ("_entry", "_parent", "_registry")

    # __slots__ 禁止动态属性添加，同时节省内存
    # Prevents dynamic attribute assignment and saves memory

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
    # 类型安全的访问器 (Typed accessors — preferred API)
    # ==================================================================

    def get_config(self, _cls: type[_C]) -> _C:
        """Return the config instance with full type safety.

        返回类型安全的配置实例。

        沿 parent 链向上查找第一个 ``config_instance`` 非 None 的节点。
        这种链表查找的时间复杂度为 O(d)，其中 d 是模块树深度。

        Args:
            _cls: 期望的 ``@config`` 装饰类，仅用于静态类型推断，
                  实际运行时不校验类型。
                  The expected ``@config`` class.  Used only for static
                  type inference; no runtime type check is performed.

        Returns:
            配置实例，类型为 *_cls*。

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

    def get_service(self, _cls: type[_S]) -> _S:
        """Return the service instance with full type safety.

        返回类型安全的当前服务/模块实例。

        内部通过 ``resolve()`` 实现，因此也支持查找兄弟服务。
        如果 *_cls* 就是当前 service 的类，直接返回 ``self._entry.instance``。

        Args:
            _cls: 期望的 ``@service`` 或 ``@module`` 装饰类。

        Returns:
            运行时实例，类型为 *_cls*。"""
        return self.resolve(_cls)

    # ==================================================================
    # 依赖解析 (Dependency resolution)
    # ==================================================================

    def resolve(self, svc_cls: type[_S]) -> _S:
        """Find and return the runtime instance of *svc_cls* in the module tree.

        在模块树中查找并返回指定服务的运行时实例。

        查找策略 (Resolution strategy):
            1. 首先检查当前 Context 绑定的 service 是否为 *_cls*
            2. 若不是，沿 parent 链向上，在每个模块的 ``sub_services``
               中按 ``__cf_name__`` 进行匹配
            3. 找到则通过 Registry 返回运行时实例
            4. 遍历完整个 parent 链仍未找到 → 抛出 ServiceNotFoundError

        为什么用 ``__cf_name__`` 匹配而不是直接用类对象比较？
        （Why match by ``__cf_name__`` and not class identity?）
        依赖声明中存储的是类引用，但 sub_services 中也是类引用——
        理论上可以直接 ``is``/``==`` 比较。但考虑未来可能支持字符串形式的
        依赖声明（如 ``deps=["db"]``），用名称匹配更加通用。

        Args:
            svc_cls: 被 ``@service`` 或 ``@module`` 装饰的类。

        Returns:
            运行时实例，类型为 *svc_cls*。

        Raises:
            ServiceNotFoundError: 当前模块及其所有祖先模块中均未找到。
        """
        name = getattr(svc_cls, "__cf_name__", svc_cls.__name__)

        # 先检查当前 entry 本身
        # First check: is this the current entry's class?
        if self._entry.cls is svc_cls or getattr(self._entry.cls, "__cf_name__", "") == name:
            return self._entry.instance  # type: ignore[return-value]

        # 沿 parent 链向上搜索
        # Walk up the parent chain
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
