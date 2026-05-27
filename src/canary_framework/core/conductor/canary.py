"""Core engine — life-cycle orchestrator for services and modules.

设计思路 (Design rationale):
    为什么叫 Canary（金丝雀）？
    （Why "Canary"?）

    金丝雀在煤矿中作为早期预警系统——框架同样用于「检测」和「编排」服务。
    The name evokes the canary in the coal mine — the framework "detects"
    and "orchestrates" services.

    为什么 config / init / start / stop 分为四个阶段？
    （Why four phases — config, init, start, stop — instead of one?）

    1. **config** — wiring 完成、配置可用，服务可以校验和调整配置
       After wiring, config is available; services validate settings.
    2. **init** — 所有服务的 config 钩子已执行，可以安全建立连接
       All config hooks have run; safe to establish connections.
    3. **start** — topo 序启动，依赖方在依赖就绪后才开始工作
       Topological start; dependants start after dependencies.
    4. **stop** — 逆序关闭，依赖方先停、被依赖方后停
       Reverse shutdown; dependants stop first.
"""

from __future__ import annotations

import inspect
from typing import Any

from canary_framework.common._logging import get_logger, init_logging
from canary_framework.common._types import ServiceEntry
from canary_framework.common.enums import LifecycleHook
from canary_framework.common.exceptions import LifecycleHookError
from canary_framework.core.algorithms.injector import inject_deps
from canary_framework.core.algorithms.naming import to_snake
from canary_framework.core.algorithms.sorter import topological_sort
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.lifecycle import HookDict, find_hooks
from canary_framework.core.decorators.module import get_module_meta, is_cf_module
from canary_framework.core.decorators.service import get_service_meta, is_cf_service


class Canary:
    """Core engine — life-cycle orchestrator for the service graph.

    框架的核心引擎，负责完整的服务生命周期编排。

    Usage::

        app = Canary(MyRootModule)
        await app.config(config=MyConfig())  # 收集 → 校验 → 排序 → wiring → on_config
        await app.init()                     # 拓扑序调用 on_init
        await app.start()                    # 拓扑序调用 on_start
        await app.stop()                     # 逆序调用 on_end
    """

    __slots__ = ("_config", "_registry", "_startup_order", "_target", "_wired")

    def __init__(self, target: type) -> None:
        self._target = target
        self._registry = Registry()
        self._startup_order: list[str] = []
        self._wired = False
        self._config: Any = None

    @property
    def registry(self) -> Registry:
        """The global :class:`Registry` (read-only after :meth:`config`)."""
        return self._registry

    @property
    def startup_order(self) -> list[str]:
        """The topological startup order computed during :meth:`config`."""
        return list(self._startup_order)

    @property
    def config_model(self) -> Any:
        """The config model passed to :meth:`config`."""
        return self._config

    # ==================================================================
    # 公开生命周期 (Public lifecycle)
    # ==================================================================

    async def config(self, *, config: Any = None) -> None:
        """Collect, validate, wire, and call ``on_config`` on every entry.

        Args:
            config: A pydantic ``BaseModel`` whose field names match service/module names.
                    Each field is either a nested ``BaseModel`` (injected as attributes)
                    or a raw dict.

        Phases:
            0. ``_collect``       — recursive discovery
            1. ``_validate``      — dependency integrity check
            2. ``topological_sort`` — Kahn BFS
            3. ``_wire_entry``    — DI + config injection + sub-service injection (per entry)
            4. ``on_config``      — user hook (topological order)
        """
        init_logging()
        engine = get_logger("engine")
        engine.info("── config start ──")

        self._config = config

        engine.debug("Phase 0: collecting services/modules")
        self._collect(self._target)

        engine.debug("Phase 1: validating dependencies")
        self._validate()

        engine.debug("Phase 2: topological sort")
        self._startup_order = topological_sort(self._registry)
        engine.info(
            "Startup order (%d): %s",
            len(self._startup_order),
            " → ".join(self._startup_order),
        )

        engine.debug("Phase 2.5: instantiating services")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            entry.instance = entry.cls()

        engine.debug("Phase 3: wiring entries")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            self._wire_entry(entry)

        engine.debug("Phase 4: on_config hooks")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.CONFIG)

        self._wired = True
        engine.info("── config complete (%d services) ──", len(self._startup_order))

    async def init(self) -> None:
        """Call ``on_init`` on every entry in topological order.

        按拓扑序触发所有服务的 on_init 钩子。
        必须在 ``config()`` 之后调用。

        Raises:
            RuntimeError: 如果 ``config()`` 尚未调用。
        """
        if not self._wired:
            raise RuntimeError("init() called before config(). Call await app.config() first.")
        engine = get_logger("engine")
        engine.info("── init start ──")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.INIT)
        engine.info("── init complete ──")

    async def start(self) -> None:
        """Call ``on_start`` on every entry in topological order.

        按拓扑序触发所有服务的 on_start 钩子。

        Raises:
            RuntimeError: 如果 ``config()`` 尚未调用。
        """
        if not self._wired:
            raise RuntimeError("start() called before config(). Call await app.config() first.")
        engine = get_logger("engine")
        engine.info("── start ──")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.START)
        engine.info("── start complete ──")

    async def stop(self) -> None:
        """Call ``on_end`` on every entry in **reverse** topological order.

        按逆序触发所有服务的 on_end 钩子。依赖方先停止，被依赖方后停止。

        Raises:
            RuntimeError: 如果 ``config()`` 尚未调用。
        """
        if not self._wired:
            raise RuntimeError("stop() called before config(). Call await app.config() first.")
        engine = get_logger("engine")
        engine.info("── stop ──")
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.END)
        engine.info("── stop complete ──")

    # ==================================================================
    # Entry wiring (framework-only)
    # ==================================================================

    def _wire_entry(self, entry: ServiceEntry) -> None:
        """Inject deps, load config from model, inject sub-services.

        Pure framework wiring — no user hooks.
        Config is looked up by ``entry.name`` in the config model.
        Nested ``BaseModel`` fields are injected as individual attributes.
        """
        engine = get_logger("engine")
        engine.info("  wire %s", entry.name)

        inject_deps(entry.instance, entry, self._registry)

        if self._config is not None:
            service_config = getattr(self._config, entry.name, None)
            if service_config is not None:
                from pydantic import BaseModel

                if isinstance(service_config, BaseModel):
                    for key, value in service_config.model_dump().items():
                        setattr(entry.instance, key, value)
                elif isinstance(service_config, dict):
                    for key, value in service_config.items():
                        setattr(entry.instance, key, value)

        if entry.sub_services:
            for sub_cls in entry.sub_services:
                sub_entry = self._registry.get_by_class(sub_cls)
                attr_name = to_snake(sub_cls.__name__)
                setattr(entry.instance, attr_name, sub_entry.instance)

    # ==================================================================
    # 钩子调度 (Hook dispatch)
    # ==================================================================

    @staticmethod
    async def _call_hook(
        entry: ServiceEntry,
        hook: LifecycleHook,
        *args: object,
    ) -> None:
        """Dispatch a lifecycle hook on *entry*.  Supports sync and async."""
        lifecycle = get_logger("lifecycle")

        if entry._hooks is None:
            raw_hooks: HookDict = find_hooks(entry.instance)
            entry._hooks = {k.value: v for k, v in raw_hooks.items()}  # type: ignore[misc]

        fn_s = entry._hooks.get(hook.value)
        if fn_s is None:
            lifecycle.debug("  %s.%s: not defined", entry.name, hook.value)
            return

        lifecycle.info("  %s.%s()", entry.name, hook.value)
        try:
            if inspect.iscoroutinefunction(fn_s):
                await fn_s(*args)
            else:
                fn_s(*args)
        except Exception as exc:
            raise LifecycleHookError(
                f"Service '{entry.name}' raised an error in {hook.value} hook: {exc}"
            ) from exc

    # ==================================================================
    # 递归收集 (Recursive collection)
    # ==================================================================

    def _collect(
        self,
        cls: type,
        parent_entry: ServiceEntry | None = None,
    ) -> None:
        """Recursively discover and register ``@service`` / ``@module`` classes."""
        if self._registry.has(cls):
            return

        registry_log = get_logger("registry")

        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, meta=meta)
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry

            registry_log.info(
                "  module %-30s services=%d",
                entry.name,
                len(meta.services),
            )
            for sub_cls in meta.services:
                self._collect(sub_cls, parent_entry=entry)
            return

        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            self._registry.register(cls, meta=svc_meta)
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry

            registry_log.info(
                "  service %-30s deps=%d",
                entry.name,
                len(entry.deps),
            )
            for dep_cls in entry.deps:
                self._collect(dep_cls, parent_entry=parent_entry)
            return

        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")

    # ==================================================================
    # 依赖校验 (Dependency validation)
    # ==================================================================

    def _validate(self) -> None:
        """Verify every ``deps=[]`` reference corresponds to a registered entry."""
        all_names = set(self._registry.names())
        for entry in self._registry.all_entries():
            for dep_name in entry.dep_names:
                if dep_name not in all_names:
                    registered = sorted(all_names) if all_names else ["(none)"]
                    raise ValueError(
                        f"Service '{entry.name}' depends on '{dep_name}', "
                        f"but '{dep_name}' is not registered. "
                        f"Registered names: {registered}"
                    )
