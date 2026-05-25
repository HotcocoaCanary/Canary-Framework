"""统一运行时上下文 —— 服务、模块、路由类的运行时句柄。

通过 parent 链实现向上委托: 配置和依赖解析沿模块树逐级查找。
Context 公开三项能力: config（配置）、service（服务实例）、resolve（依赖解析）。

Context 层次:
    EngineContext (未来扩展) → 根模块 Context → 子模块 Context → 服务 Context
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from canary_framework.core.registry.registry import Registry, ServiceEntry


class Context:
    """统一运行时上下文，通过 parent 链提供配置查找和服务解析。

    服务和模块的 on_init 钩子以及路由类的 __init__ 均接收此 Context 对象。

    Attributes:
        config:  沿 parent 链向上查找第一个有 config_instance 的节点。
        service: 当前 Context 绑定的服务/模块实例。
        resolve: 沿 parent 链在父模块的 sub_services 中查找已注册的服务实例。
    """

    def __init__(
        self,
        entry: ServiceEntry,  # 绑定的注册项
        parent: Context | None,  # 父模块的 Context，根模块为 None
        registry: Registry,  # 全局注册表，供 resolve() 使用
    ) -> None:
        self._entry = entry
        self._parent = parent
        self._registry = registry

    @property
    def config(self) -> object:
        """沿 parent 链向上查找第一个已加载的配置实例。

        查找策略: 当前节点有 config_instance → 返回；否则沿 parent 链上溯。
        整条链路都没有配置时抛出 RuntimeError。

        Raises:
            RuntimeError: 整条 parent 链都未找到配置实例。
        """
        cur: Context | None = self
        while cur is not None:
            if cur._entry is not None and cur._entry.config_instance is not None:
                return cur._entry.config_instance
            cur = cur._parent
        raise RuntimeError("No config bound to this context chain.")

    @property
    def service(self) -> object:
        """当前上下文绑定的服务/模块的运行时实例。"""
        return self._entry.instance

    def resolve(self, svc_cls: type) -> object:
        """沿 parent 链在父模块的 sub_services 中查找并返回指定类型的服务实例。

        查找策略: 从当前节点开始，沿 parent 链向上，检查每个模块的 sub_services
        列表，按 __cf_name__ 匹配类名。找到后通过 Registry 返回运行时实例。

        Args:
            svc_cls: 要查找的 @service 或 @module 装饰的类。

        Returns:
            该类的运行时实例。

        Raises:
            KeyError: 整个 parent 链中均未找到该服务。
        """
        name = getattr(svc_cls, "__cf_name__", svc_cls.__name__)
        cur: Context | None = self
        while cur is not None:
            entry = cur._entry
            if entry is not None and entry.is_module:
                for sub_cls in entry.sub_services:
                    if getattr(sub_cls, "__cf_name__", "") == name:
                        return self._registry.get_instance(sub_cls)
            cur = cur._parent

        raise KeyError(
            f"Service '{name}' not found in this module or any parent module. "
            f"Ensure it is registered as a sub-service of a parent @module."
        )
