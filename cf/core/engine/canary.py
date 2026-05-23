# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

import asyncio
import logging

from cf.core.decorators.lifecycle import find_hooks
from cf.core.decorators.module import is_cf_module, get_module_meta
from cf.core.decorators.service import is_cf_service, get_service_meta
from cf.core.engine.context import Context
from cf.core.engine.injector import inject_deps
from cf.core.engine.sorter import topological_sort
from cf.core.registry.registry import Registry, ServiceEntry

logger = logging.getLogger("cf")


class Canary:

    def __init__(self, target: type) -> None:
        self._target = target               # 根模块/服务类
        self._registry = Registry()         # 注册中心
        self._startup_order: list[str] = [] # 拓扑排序后的名称列表

    @property
    def registry(self) -> Registry:
        # 公开 Registry，供子类（WebCanary）和外部访问
        return self._registry

    # ── 公开生命周期方法 ─────────────────────────────────

    async def init(self) -> None:
        # 阶段0：递归收集 → 注册 → 父子关系 → config_cls 继承
        self._collect(self._target)

        # 阶段1：校验依赖
        self._validate()

        # 阶段2：拓扑排序
        self._startup_order = topological_sort(self._registry)

        # 阶段3：构建 Context 链
        self._build_context_tree(self._target, parent_ctx=None)

        # 阶段4：按拓扑序注入依赖 → 加载配置 → 调 on_init
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            inject_deps(entry.instance, entry, self._registry)

            # 配置由 pydantic-settings 自动加载：
            #   @config 装饰器已在 model_config 中设置 env_file=".env"
            #   用户只需在 @config 类中声明字段和默认值，pydantic-settings 自动读取环境变量和 .env 文件
            if entry.config_cls is not None:
                entry.config_instance = entry.config_cls()

            await self._call_hook(entry, "on_init", entry.context)

    async def start(self) -> None:
        # 按拓扑序调 on_start
        for name in self._startup_order:
            await self._call_hook(self._registry.get_by_name(name), "on_start")

    async def stop(self) -> None:
        # 按逆序调 on_end
        for name in reversed(self._startup_order):
            await self._call_hook(self._registry.get_by_name(name), "on_end")

    # ── 统一钩子调用 ────────────────────────────────────

    @staticmethod
    async def _call_hook(entry: ServiceEntry, hook_name: str, *args: object) -> None:
        # 钩子只查找一次，缓存在 entry._hooks 上
        if entry._hooks is None:
            entry._hooks = find_hooks(entry.instance)
        fn = entry._hooks.get(hook_name)
        if fn is None:
            return
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result

    # ── _collect ─────────────────────────────────────────

    def _collect(
        self,
        cls: type,
        parent_entry: ServiceEntry | None = None,
    ) -> None:
        if self._registry.has(cls):
            return

        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)
            for sub_cls in meta.get("services", []):
                self._collect(sub_cls, parent_entry=entry)
            return

        if is_cf_service(cls):
            meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=meta)
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)
            return

        raise TypeError(
            f"'{cls.__name__}' is not decorated with @service or @module"
        )

    def _inherit_config(
        self, entry: ServiceEntry, parent_entry: ServiceEntry | None
    ) -> None:
        if entry.config_cls is None and parent_entry is not None:
            entry.config_cls = parent_entry.config_cls

    # ── _build_context_tree ──────────────────────────────

    def _build_context_tree(
        self,
        cls: type,
        parent_ctx: Context | None,
    ) -> None:
        entry = self._registry.get_by_class(cls)
        ctx = Context(entry=entry, parent=parent_ctx, registry=self._registry)
        entry.context = ctx

        if entry.is_module:
            for sub_cls in entry.sub_services:
                self._build_context_tree(sub_cls, parent_ctx=ctx)

    # ── _validate ────────────────────────────────────────

    def _validate(self) -> None:
        all_names = set(self._registry.names())
        for entry in self._registry.all_entries():
            for dep_name in entry.dep_names:
                if dep_name not in all_names:
                    raise ValueError(
                        f"Service '{entry.name}' depends on '{dep_name}', "
                        f"but '{dep_name}' is not registered. "
                        f"Registered: {sorted(all_names)}"
                    )
