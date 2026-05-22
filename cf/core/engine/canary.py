"""
Canary 核心引擎 —— 负责整个框架的启动生命周期编排。

设计原则：
    - _collect: 只做 class 级别的收集和 config_cls 继承（子服务未声明 config → 继承父模块的）
    - _init:   只做实例级别的事：依赖注入 → 用根 config_file_path 实例化配置 → on_init 钩子
    - 所有服务/模块统一从 Canary.init(config_file_path=".env") 传入的路径加载配置，不存在任何配置路径传播
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from cf.core.decorators.lifecycle import find_hooks
from cf.core.decorators.module import is_cf_module, get_module_meta
from cf.core.decorators.service import is_cf_service, get_service_meta
from cf.core.engine.context import Context
from cf.core.engine.injector import inject_deps
from cf.core.engine.sorter import topological_sort
from cf.core.registry.registry import Registry, ServiceEntry

logger = logging.getLogger("cf")


def _instantiate_config(config_cls: type | None, env_file: str) -> object | None:
    """实例化 @config 类，通过 _env_file 加载指定的 .env 文件。"""
    if config_cls is None:
        return None
    resolved = str(Path(env_file).resolve())

    return config_cls(_env_file=resolved)  # type: ignore[call-arg]


class Canary:
    """Canary 引擎 —— 服务/模块的启动与停止编排器。"""

    def __init__(self, target: type) -> None:
        self._target = target
        self._registry = Registry()
        self._startup_order: list[str] = []

    async def init(self, config_file_path: str = ".env") -> None:
        """
        初始化阶段。

        参数：
            config_file_path: 全局唯一的配置文件路径，所有服务/模块统一从此加载配置

        流程：
            1. _collect:  递归发现所有 class → 注册到 Registry → 完成 config_cls 继承
            2. _validate: 校验依赖完整性
            3. 拓扑排序:  计算启动顺序
            4. _init:     按拓扑序逐一初始化实例
        """
        self._root_config_path = config_file_path
        self._collect(self._target)
        self._validate()
        self._startup_order = topological_sort(self._registry)

        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._init(entry)

    async def start(self) -> None:
        """启动阶段 —— 按拓扑序调用 @on_start 钩子。"""
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._start(entry)

    async def stop(self) -> None:
        """停止阶段 —— 按拓扑序逆序调用 @on_end 钩子。"""
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._stop(entry)

    # ── _collect ──────────────────────────────────────────────

    def _collect(
            self,
            cls: type,
            parent_module: ServiceEntry | None = None,
    ) -> None:
        """
        递归收集服务/模块 class，注册到 Registry。

        模块和服务共用同一套注册 + config_cls 继承逻辑，
        唯一区别：模块会递归收集其 services 列表中的子节点。

        参数：
            cls:           当前要注册的类
            parent_module: 父模块的 ServiceEntry，用于 config_cls 继承
        """
        if self._registry.has(cls):
            return

        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)
            entry = self._registry.get_by_class(cls)
            self._inherit_config(entry, parent_module)

            for sub_cls in meta.get("services", []):
                self._collect(sub_cls, parent_module=entry)
            return

        if is_cf_service(cls):
            meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=meta)
            entry = self._registry.get_by_class(cls)
            self._inherit_config(entry, parent_module)
            return

        raise TypeError(
            f"'{cls.__name__}' is not decorated with @service or @module"
        )

    def _inherit_config(
            self, entry: ServiceEntry, parent_module: ServiceEntry | None
    ) -> None:
        """子服务未声明 config_cls 时，继承父模块的 config_cls。"""
        if entry.config_cls is None and parent_module is not None:
            entry.config_cls = parent_module.config_cls

    # ── _validate ─────────────────────────────────────────────

    def _validate(self) -> None:
        """校验 @service(deps=[...]) 中所有依赖是否都已注册。"""
        all_names = set(self._registry.names())
        for entry in self._registry.all_entries():
            for dep_name in entry.dep_names:
                if dep_name not in all_names:
                    raise ValueError(
                        f"Service '{entry.name}' depends on '{dep_name}', "
                        f"but '{dep_name}' is not registered. "
                        f"Registered: {sorted(all_names)}"
                    )

    # ── _init ──────────────────────────────────────────────────

    async def _init(self, entry: ServiceEntry) -> None:
        """
        单个服务/模块的实例初始化。

        三件事：
        1. 依赖注入
        2. 用全局 config_file_path 实例化配置
        3. 构建上下文 + 调用 @on_init 钩子
        """
        inject_deps(entry.instance, entry, self._registry)

        config_instance = _instantiate_config(entry.config_cls, self._root_config_path)
        entry.config_instance = config_instance

        ctx = Context(config_instance)

        hooks = find_hooks(entry.instance)
        on_init = hooks.get("on_init")
        if on_init:
            result = on_init(ctx)
            if asyncio.iscoroutine(result):
                await result

    # ── _start / _stop ─────────────────────────────────────────

    async def _start(self, entry: ServiceEntry) -> None:
        hooks = find_hooks(entry.instance)
        on_start = hooks.get("on_start")
        if on_start:
            result = on_start()
            if asyncio.iscoroutine(result):
                await result

    async def _stop(self, entry: ServiceEntry) -> None:
        hooks = find_hooks(entry.instance)
        on_end = hooks.get("on_end")
        if on_end:
            result = on_end()
            if asyncio.iscoroutine(result):
                await result
