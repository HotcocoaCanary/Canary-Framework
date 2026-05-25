"""Core engine — life-cycle orchestrator for services and modules.

:class:`Canary` is the central entry point.  It manages the complete
application life-cycle through four phases:

    =============  ======================================================
    Phase           Description
    =============  ======================================================
    ``_collect``    Recursively discover ``@service`` / ``@module`` classes
    ``_validate``   Verify all ``deps=[]`` references are registered
    ``topo sort``   Kahn's BFS — compute safe startup order
    ``_init_entry`` DI → config loading → ``on_init`` hook (per entry)
    =============  ======================================================

Logging:
    The framework uses the ``"cf"`` logger namespace (e.g. ``cf.engine``,
    ``cf.config``, ``cf.lifecycle``).  Set ``CF_LOG_LEVEL`` to control
    verbosity (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).  The logger
    does **not** propagate to the root logger, avoiding duplicate output
    from uvicorn or other libraries.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from canary_framework.core.decorators.lifecycle import (
    HookDict,
    LifecycleHook,
    find_hooks,
)
from canary_framework.core.decorators.module import get_module_meta, is_cf_module
from canary_framework.core.decorators.service import get_service_meta, is_cf_service
from canary_framework.core.engine.context import Context
from canary_framework.core.engine.injector import inject_deps
from canary_framework.core.engine.sorter import topological_sort
from canary_framework.core.registry.registry import Registry, ServiceEntry
from canary_framework.exceptions import LifecycleHookError

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_cf_logger = logging.getLogger("cf")

_SENSITIVE_RE = re.compile(
    r"(password|passwd|secret|token|key|api_key|auth|credential|private)",
    re.IGNORECASE,
)
"""Regex matching config field names that should be masked in logs."""


def _init_logging() -> None:
    """Initialise the framework logger (idempotent).

    Reads ``CF_LOG_LEVEL`` from the environment (default ``INFO``).
    Configures a :class:`~logging.StreamHandler` with the format
    ``[CF] [LEVEL] [logger] message`` and disables root propagation.
    """
    level_name = os.environ.get("CF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    _cf_logger.setLevel(level)

    if _cf_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[CF] [%(levelname)-5s] [%(name)s] %(message)s"))
    _cf_logger.addHandler(handler)
    _cf_logger.propagate = False
    _cf_logger.debug("Logging initialised at level=%s", level_name)


def _get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``cf`` namespace."""
    return logging.getLogger(f"cf.{name}")


def _sanitize_config_values(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive values replaced by ``'***'``.

    A field is considered sensitive if its name (case-insensitive)
    contains any of: ``password``, ``passwd``, ``secret``, ``token``,
    ``key``, ``api_key``, ``auth``, ``credential``, ``private``.
    """
    return {k: "***" if _SENSITIVE_RE.search(k) else v for k, v in data.items()}


# ---------------------------------------------------------------------------
# Canary
# ---------------------------------------------------------------------------


class Canary:
    """Core engine — life-cycle orchestrator for the service graph.

    Usage::

        app = Canary(MyRootModule)
        await app.init()
        await app.start()
        # … application runs …
        await app.stop()

    :meth:`init` performs collection, validation, topological sort,
    context-tree construction, dependency injection, config loading,
    and ``on_init`` hook dispatch — in that order.
    """

    __slots__ = ("_registry", "_startup_order", "_target")

    def __init__(self, target: type) -> None:
        """Create a :class:`Canary` instance for the given root class.

        Args:
            target: A ``@module``- or ``@service``-decorated class that
                serves as the entry point for the service graph.
        """
        self._target = target
        self._registry = Registry()
        self._startup_order: list[str] = []

    @property
    def registry(self) -> Registry:
        """The global :class:`Registry` (read-only after :meth:`init`)."""
        return self._registry

    @property
    def startup_order(self) -> list[str]:
        """The topological startup order computed during :meth:`init`."""
        return list(self._startup_order)

    # ------------------------------------------------------------------
    # Public life-cycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """Initialise the service graph.

        Phases executed in order:
            1. ``_collect()``       — recursive discovery
            2. ``_validate()``      — dependency integrity check
            3. ``topological_sort()`` — Kahn BFS
            4. ``_build_context_tree()`` — Context parent chain
            5. Per-entry: DI → config → ``on_init``
        """
        _init_logging()
        engine = _get_logger("engine")
        engine.info("── init start ──")

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

        engine.debug("Phase 3: building context tree")
        self._build_context_tree(self._target, parent_ctx=None)

        engine.debug("Phase 4: initialising entries")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._init_entry(entry)

        engine.info("── init complete (%d services) ──", len(self._startup_order))

    async def start(self) -> None:
        """Start all services in topological order.

        Calls ``on_start`` on every registered entry.
        """
        engine = _get_logger("engine")
        engine.info("── start ──")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.START)
        engine.info("── start complete ──")

    async def stop(self) -> None:
        """Stop all services in **reverse** topological order.

        Calls ``on_end`` on every registered entry, starting with the
        most dependent service and ending with the least dependent.
        """
        engine = _get_logger("engine")
        engine.info("── stop ──")
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.END)
        engine.info("── stop complete ──")

    # ------------------------------------------------------------------
    # Entry initialisation
    # ------------------------------------------------------------------

    async def _init_entry(self, entry: ServiceEntry) -> None:
        """Initialise a single service/module.

        Steps:
            1. Dependency injection (``inject_deps``)
            2. Config loading (if ``config_cls`` is set)
            3. ``on_init`` hook
        """
        engine = _get_logger("engine")
        config_log = _get_logger("config")

        engine.info("  init %s", entry.name)

        # 1. Dependency injection
        inject_deps(entry.instance, entry, self._registry)

        # 2. Config loading
        if entry.config_cls is not None:
            entry.config_instance = entry.config_cls()
            raw_cfg = {
                k: v for k, v in vars(entry.config_instance).items() if not k.startswith("_")
            }
            config_log.info(
                "  %s config loaded: %s",
                entry.name,
                _sanitize_config_values(raw_cfg),
            )
        else:
            config_log.debug("  %s has no config", entry.name)

        # 3. on_init hook
        await self._call_hook(entry, LifecycleHook.INIT, entry.context)

    # ------------------------------------------------------------------
    # Hook dispatch
    # ------------------------------------------------------------------

    @staticmethod
    async def _call_hook(
        entry: ServiceEntry,
        hook: LifecycleHook,
        *args: object,
    ) -> None:
        """Dispatch a lifecycle hook on *entry*.

        The hook lookup result is cached in ``entry._hooks`` so each
        instance's ``dir()`` is scanned at most once.

        Supports both synchronous and asynchronous hook methods:
        :func:`asyncio.iscoroutine` detects the return type and adapts.
        """
        lifecycle = _get_logger("lifecycle")

        if entry._hooks is None:
            raw_hooks: HookDict = find_hooks(entry.instance)
            # Convert LifecycleHook keys to strings for cache storage
            entry._hooks = {k.value: v for k, v in raw_hooks.items()}  # type: ignore[misc]

        fn_s = entry._hooks.get(hook.value)
        if fn_s is None:
            lifecycle.debug("  %s.%s: not defined", entry.name, hook.value)
            return

        lifecycle.info("  %s.%s()", entry.name, hook.value)
        try:
            result = fn_s(*args)
        except Exception as exc:
            raise LifecycleHookError(
                f"Service '{entry.name}' raised an error in {hook.value} hook: {exc}"
            ) from exc

        if asyncio.iscoroutine(result):
            await result

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def _collect(
        self,
        cls: type,
        parent_entry: ServiceEntry | None = None,
    ) -> None:
        """Recursively discover and register ``@service`` / ``@module`` classes.

        Modules are recursed into via their ``services`` list; services
        are leaf nodes.

        Configuration inheritance: a child entry with ``config_cls=None``
        inherits the config class from its parent module.
        """
        if self._registry.has(cls):
            return

        registry_log = _get_logger("registry")

        # ── Module branch ──────────────────────────────────────────
        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)  # type: ignore[arg-type]
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)

            registry_log.info(
                "  module %-30s config=%s  services=%d",
                entry.name,
                entry.config_cls.__name__ if entry.config_cls else "inherit",
                len(meta.get("services", ())),
            )
            for sub_cls in meta.get("services", ()):
                self._collect(sub_cls, parent_entry=entry)
            return

        # ── Service branch ─────────────────────────────────────────
        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=svc_meta)  # type: ignore[arg-type]
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)

            registry_log.info(
                "  service %-30s config=%s  deps=%d",
                entry.name,
                entry.config_cls.__name__ if entry.config_cls else "inherit",
                len(entry.deps),
            )
            return

        raise TypeError(
            f"'{cls.__name__}' is not decorated with @service or @module. "
            f"Only framework-decorated classes can be passed to Canary."
        )

    @staticmethod
    def _inherit_config(
        entry: ServiceEntry,
        parent_entry: ServiceEntry | None,
    ) -> None:
        """Copy *config_cls* from parent when the child has none."""
        if entry.config_cls is None and parent_entry is not None:
            entry.config_cls = parent_entry.config_cls

    # ------------------------------------------------------------------
    # Context tree
    # ------------------------------------------------------------------

    def _build_context_tree(
        self,
        cls: type,
        parent_ctx: Context | None,
    ) -> None:
        """Build the :class:`Context` parent chain for the module tree.

        Each :class:`ServiceEntry` gets a :class:`Context` whose parent
        is the enclosing module's context.  The root module's parent is
        ``None``.
        """
        entry = self._registry.get_by_class(cls)
        ctx = Context(entry=entry, parent=parent_ctx, registry=self._registry)
        entry.context = ctx

        if entry.is_module:
            for sub_cls in entry.sub_services:
                self._build_context_tree(sub_cls, parent_ctx=ctx)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Verify every ``deps=[]`` reference corresponds to a registered entry.

        Raises:
            ValueError: If any dependency name is not found in the registry.
        """
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
