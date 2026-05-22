from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from cf.core.context.module_ctx import ModuleContext
from cf.core.context.service_ctx import ServiceContext
from cf.core.decorators.lifecycle import find_hooks
from cf.core.decorators.module import is_cf_module, get_module_meta
from cf.core.decorators.service import is_cf_service, get_service_meta
from cf.core.engine.injector import inject_deps
from cf.core.engine.sorter import topological_sort
from cf.core.registry.registry import Registry, ServiceEntry

logger = logging.getLogger("cf")


def _configure_logging(log_level: str, log_format: str) -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.NOTSET,
            format=log_format,
        )
    root.setLevel(log_level.upper())


def _resolve_config_path(entry: ServiceEntry, parent_path: str | None = None) -> str:
    if entry.config_file_path:
        return entry.config_file_path
    if parent_path:
        return parent_path
    return ".env"


def _instantiate_config(config_cls: type | None, env_file: str) -> object | None:
    if config_cls is None:
        return None
    resolved = str(Path(env_file).resolve())
    import pydantic_settings

    return config_cls(_env_file=resolved)  # type: ignore[call-arg]


class Canary:
    def __init__(
            self,
            target: type,
            *,
            config_file_path: str = ".env",
            log_level: str = "INFO",
            log_format: str = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    ) -> None:
        self._target = target
        self._root_config_path = config_file_path
        self._registry = Registry()
        self._startup_order: list[str] = []
        _configure_logging(log_level, log_format)

    def start(self) -> None:
        asyncio.run(self._startup())

    def stop(self) -> None:
        asyncio.run(self._shutdown())

    async def _startup(self) -> None:
        self._collect(self._target)
        self._validate()
        self._startup_order = topological_sort(self._registry)

        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._init(entry)

        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._start(entry)

    async def _shutdown(self) -> None:
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._stop(entry)

    def _collect(self, cls: type, parent_path: str | None = None) -> None:
        if self._registry.has(cls):
            return

        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)

            mod_path = meta.get("config_file_path") or parent_path or self._root_config_path

            for sub_cls in meta.get("services", []):
                self._collect(sub_cls, parent_path=mod_path)
            return

        if is_cf_service(cls):
            meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=meta)
            return

        raise TypeError(
            f"'{cls.__name__}' is not decorated with @service or @module"
        )

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

    async def _init(self, entry: ServiceEntry) -> None:
        inject_deps(entry.instance, entry, self._registry)

        parent_module = None
        if not entry.is_module:
            for mod_entry in self._registry.all_entries():
                if mod_entry.is_module and entry.cls in mod_entry.sub_services:
                    parent_module = mod_entry
                    break

        parent_path = None
        if not entry.config_file_path:
            if parent_module is not None:
                parent_path = parent_module.config_file_path or self._root_config_path
            else:
                parent_path = self._root_config_path

        env_file = _resolve_config_path(entry, parent_path)

        config_cls = entry.config_cls
        if config_cls is None and not entry.is_module and parent_module is not None:
            config_cls = parent_module.config_cls

        config_instance = _instantiate_config(config_cls, env_file)

        if entry.is_module:
            ctx: Any = ModuleContext(config_instance)
        else:
            ctx = ServiceContext(config_instance)

        hooks = find_hooks(entry.instance)

        on_init = hooks.get("on_init")
        if on_init:
            result = on_init(ctx)
            if asyncio.iscoroutine(result):
                await result

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
