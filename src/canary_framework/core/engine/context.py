"""Unified runtime context — the service/module's connection to the framework.

Each ``@service`` or ``@module`` instance receives a :class:`Context` during
initialisation.  The context provides three capabilities:

1. **Configuration** — :meth:`config_as` returns the typed config instance.
2. **Service access** — :meth:`service_as` returns a typed sibling service.
3. **Dependency resolution** — :meth:`resolve` traverses the module tree
   upward to find a service by class.

Context parent chain:
    Root module context → child module context → service context → …
    Each context delegates lookups upward via its ``_parent`` reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from canary_framework.exceptions import ConfigurationError, ServiceNotFoundError

if TYPE_CHECKING:
    from canary_framework.core.registry.registry import Registry, ServiceEntry

_C = TypeVar("_C")
"""Config type for :meth:`config_as`."""

_S = TypeVar("_S")
"""Service type for :meth:`service_as` and :meth:`resolve`."""


class Context:
    """Unified runtime context for a service or module instance.

    Provided to ``@on_init`` hooks and ``@router`` constructors.

    The parent chain enables upward delegation: if the current node does
    not hold a config instance, the lookup continues to the parent
    module's context, and so on until the root.
    """

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

    # ------------------------------------------------------------------
    # Typed accessors
    # ------------------------------------------------------------------

    def config_as(self, _cls: type[_C]) -> _C:
        """Return the config instance with full type safety.

        Traverses the parent chain upward to find the first node whose
        :attr:`ServiceEntry.config_instance` is not ``None``.

        Args:
            _cls: The ``@config``-decorated class expected at this point
                in the module tree.  Used only for static type inference;
                the actual runtime instance must be compatible.

        Returns:
            The config instance, typed as *_cls*.

        Raises:
            ConfigurationError: If no config instance is found in the
                entire parent chain.

        Example::

            @on_init
            def init(self, ctx: Context) -> None:
                cfg = ctx.config_as(AppConfig)
                print(cfg.host)  # typed as str
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

    def config(self) -> object:
        """Return the **untyped** config instance.

        .. deprecated:: 0.2
            Prefer :meth:`config_as` for type-safe access.

        Traverses the parent chain to find the first config instance.
        """
        return self.config_as(object)

    def service_as(self, _cls: type[_S]) -> _S:
        """Return the service instance with full type safety.

        Shortcut for ``ctx.resolve(SomeService)`` — resolves the service
        class to its runtime instance.

        Args:
            _cls: The ``@service`` class to retrieve.

        Returns:
            The runtime instance, typed as *_cls*.

        Raises:
            ServiceNotFoundError: If the service is not found in the
                current module or any ancestor module.
        """
        return self.resolve(_cls)

    def service(self) -> object:
        """Return the **untyped** current service/module instance.

        .. deprecated:: 0.2
            Prefer :meth:`service_as` for type-safe access.
        """
        return self._entry.instance

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def resolve(self, svc_cls: type[_S]) -> _S:
        """Find and return the runtime instance of *svc_cls* in the module tree.

        Walks the parent chain upward.  At each module node, scans the
        module's ``sub_services`` for a class whose ``__cf_name__``
        matches *svc_cls*'s name.  Also checks whether *svc_cls* is the
        class of the current entry itself.

        Args:
            svc_cls: A ``@service`` or ``@module``-decorated class.

        Returns:
            The runtime instance, typed as *svc_cls*.

        Raises:
            ServiceNotFoundError: If *svc_cls* is not found in the
                current module or any ancestor module.

        Example::

            @on_init
            def init(self, ctx: Context) -> None:
                db = ctx.resolve(DBService)
                db.execute("SELECT 1")
        """
        name = getattr(svc_cls, "__cf_name__", svc_cls.__name__)

        # Check the current entry itself
        if self._entry.cls is svc_cls or getattr(self._entry.cls, "__cf_name__", "") == name:
            return self._entry.instance  # type: ignore[return-value]

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
