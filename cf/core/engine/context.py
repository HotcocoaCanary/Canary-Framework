# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 仅在类型检查时导入，避免运行时的循环引用
    from cf.core.registry.registry import Registry, ServiceEntry


class Context:
    # 统一运行时上下文，服务和模块共用。
    # 通过 parent 链实现向上查找：config 找不到 → 找父模块的 config；resolve 找不到 → 找父模块注册的子服务。

    def __init__(
        self,
        entry: ServiceEntry,         # 当前上下文绑定的注册项（服务或模块）
        parent: Context | None,      # 父上下文，根模块为 None。形成树链：根模块 → 子模块 → 服务
        registry: Registry,          # 全局注册表，供 resolve() 根据类型获取实例
    ) -> None:
        self._entry = entry            # 绑定到的 ServiceEntry
        self._parent = parent          # 父模块上下文（沿此链向上查找 config 和服务）
        self._registry = registry      # 全局注册表

    # ── config：沿父链向上查找配置实例 ─────────────────────

    @property
    def config(self) -> object:
        # 从当前节点开始，沿 parent 链向上遍历
        cur = self
        while cur is not None:
            # 如果当前 Context 绑定的 entry 有配置实例，直接返回
            if cur._entry is not None and cur._entry.config_instance is not None:
                return cur._entry.config_instance
            # 当前没有，上溯到父模块上下文继续查找
            cur = cur._parent
        # 整条链路都没有配置，抛出异常
        raise RuntimeError("No config bound to this context chain.")

    # ── service：当前上下文绑定的服务/模块实例 ─────────────

    @property
    def service(self) -> object:
        # 直接暴露 entry 中的实例对象（服务或模块的运行时实例）
        return self._entry.instance

    # ── resolve：沿父链向上查找已注册的子服务 ──────────────

    def resolve(self, svc_cls: type) -> object:
        # 获取目标服务的名称（@service 或 @module 声明的 name）
        name = getattr(svc_cls, '__cf_name__', svc_cls.__name__)

        # 沿 parent 链从当前节点向上逐级查找
        cur = self
        while cur is not None:
            entry = cur._entry
            # 只有模块才有 sub_services，服务节点的 sub_services 为空
            if entry is not None and entry.is_module:
                # 遍历当前模块注册的所有子服务
                for sub_cls in entry.sub_services:
                    # 按 __cf_name__ 比对（与注册表中的名称一致）
                    if getattr(sub_cls, '__cf_name__', '') == name:
                        # 找到后通过全局注册表获取其运行时实例
                        return self._registry.get_instance(sub_cls)
            # 当前模块未找到，上溯父模块
            cur = cur._parent

        # 整个父链都没找到该服务
        raise KeyError(
            f"Service '{name}' not found in this module or any parent module. "
            f"Ensure it is registered as a sub-service of a parent @module."
        )
