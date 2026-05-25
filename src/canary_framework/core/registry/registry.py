"""Registry — central index of all registered services and modules.

:class:`ServiceEntry` is a :func:`dataclass(slots=True) <dataclasses.dataclass>`
that holds the complete runtime state of a single service or module.
:class:`Registry` provides O(1) lookup by name or class and is the
single source of truth during collection, validation, and initialisation.

Life-cycle of a ServiceEntry:
    1. **Created** by :meth:`Registry.register` during ``_collect()``.
    2. **parent_entry** / **sub_services** populated as the module tree
       is traversed.
    3. **dep_names** resolved from *deps* list during registration.
    4. **config_instance** built in :meth:`~canary_framework.core.engine.canary.Canary._init_entry`.
    5. **context** assigned in :meth:`~canary_framework.core.engine.canary.Canary._build_context_tree`.
    6. **_hooks** lazily populated on first hook invocation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from canary_framework.core.engine.context import Context

from canary_framework.exceptions import ServiceNotFoundError


@dataclass(slots=True)
class ServiceEntry:
    """Runtime descriptor for a single ``@service`` or ``@module`` instance.

    Created during collection, progressively enriched during init/start/stop.
    """

    cls: type
    """The original user class decorated with ``@service`` or ``@module``."""

    instance: object
    """The constructed instance (``cls()`` called with no arguments)."""

    name: str
    """Globally unique name declared in the decorator."""

    deps: list[type] = field(default_factory=list)
    """List of dependency classes (from ``deps=[]``).  Used for DI."""

    config_cls: type | None = None
    """``@config``-decorated class, or ``None`` to inherit from parent."""

    is_module: bool = False
    """``True`` for ``@module``, ``False`` for ``@service``."""

    sub_services: list[type] = field(default_factory=list)
    """Child ``@service`` / ``@module`` classes declared in the module's
    ``services=[]`` list.  Only meaningful when *is_module* is ``True``."""

    dep_names: list[str] = field(default_factory=list)
    """Resolved dependency names (from each class in *deps*) for the topological sorter."""

    config_instance: object | None = field(default=None, repr=False)
    """Constructed pydantic-settings instance, set during :meth:`_init_entry`."""

    parent_entry: ServiceEntry | None = field(default=None, repr=False, compare=False)
    """Parent module's :class:`ServiceEntry` (``None`` for the root module)."""

    context: Context | None = field(default=None, repr=False, compare=False)
    """Associated :class:`~canary_framework.core.engine.context.Context`,
    assigned during context-tree construction."""

    _hooks: dict[str, Callable[..., Any]] | None = field(default=None, repr=False, compare=False)
    """Cached result of :func:`~canary_framework.core.decorators.lifecycle.find_hooks`.
    Populated lazily on first hook invocation to avoid scanning every
    instance's ``dir()`` during startup."""


class Registry:
    """Central registry — O(1) lookup by name or class for all
    ``@service`` / ``@module`` instances.

    The registry is populated during :meth:`~canary_framework.core.engine.canary.Canary._collect`
    and then treated as **immutable** during the remaining life-cycle
    (:meth:`init` / :meth:`start` / :meth:`stop`).  This single-writer,
    multiple-reader pattern eliminates the need for synchronisation
    primitives in the common case.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        cls: type,
        *,
        is_module: bool = False,
        sub_services: list[type] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Register a ``@service`` or ``@module`` class.

        Idempotent: if *cls* is already registered the call is a no-op.

        When *meta* is ``None``, metadata is read from the decorator
        attributes attached to *cls* (:func:`get_service_meta` /
        :func:`get_module_meta`).

        Args:
            cls: The user class to register.
            is_module: ``True`` for modules, ``False`` for services.
            sub_services: Child classes (modules only).
            meta: Pre-resolved metadata dict.  If ``None``, read from cls.

        Raises:
            ValueError: If *name* is already registered under a
                different class.
        """
        if cls in self._by_class:
            return

        if meta is None:
            if is_module:
                from canary_framework.core.decorators.module import (
                    get_module_meta,
                )

                raw: object = get_module_meta(cls)
            else:
                from canary_framework.core.decorators.service import (
                    get_service_meta,
                )

                raw = get_service_meta(cls)
            assert isinstance(raw, dict)
            meta = raw

        name: str = meta["name"]
        if name in self._by_name:
            raise ValueError(
                f"Service/Module '{name}' is already registered. "
                f"Each @service and @module must have a globally unique name."
            )

        instance = cls()

        entry = ServiceEntry(
            cls=cls,
            instance=instance,
            name=name,
            deps=list(meta.get("deps", ())),
            config_cls=meta.get("config_cls"),
            is_module=is_module,
            sub_services=list(meta.get("services", ())) if is_module else [],
        )

        entry.dep_names = [
            d if isinstance(d, str) else getattr(d, "__cf_name__", d.__name__) for d in entry.deps
        ]

        self._by_name[name] = entry
        self._by_class[cls] = entry

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_by_name(self, name: str) -> ServiceEntry:
        """Look up a registered entry by its unique name.

        Args:
            name: The service/module name declared in ``@service(name=...)``
                or ``@module(name=...)``.

        Returns:
            The corresponding :class:`ServiceEntry`.

        Raises:
            ServiceNotFoundError: If *name* is not registered.
        """
        try:
            return self._by_name[name]
        except KeyError:
            raise ServiceNotFoundError(
                f"'{name}' is not registered. Registered names: {sorted(self._by_name)}"
            ) from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        """Look up a registered entry by its original class object.

        Args:
            cls: The class decorated with ``@service`` or ``@module``.

        Returns:
            The corresponding :class:`ServiceEntry`.

        Raises:
            ServiceNotFoundError: If *cls* is not registered.
        """
        try:
            return self._by_class[cls]
        except KeyError:
            raise ServiceNotFoundError(
                f"'{cls.__name__}' is not registered. "
                f"Has it been decorated with @service or @module?"
            ) from None

    def get_instance(self, cls: type) -> object:
        """Return the runtime instance for the given class.

        Raises:
            ServiceNotFoundError: If *cls* is not registered.
        """
        return self.get_by_class(cls).instance

    def has(self, cls: type) -> bool:
        """Return ``True`` if *cls* is registered."""
        return cls in self._by_class

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def all_entries(self) -> list[ServiceEntry]:
        """Return all registered entries (no guaranteed order)."""
        return list(self._by_name.values())

    def names(self) -> list[str]:
        """Return the names of all registered entries."""
        return list(self._by_name.keys())

    def __len__(self) -> int:
        """Number of registered entries."""
        return len(self._by_name)

    def __contains__(self, cls: type) -> bool:
        """Check if *cls* is registered."""
        return cls in self._by_class

    def __iter__(self) -> Iterator[ServiceEntry]:
        """Iterate over all registered :class:`ServiceEntry` objects."""
        return iter(self._by_name.values())
