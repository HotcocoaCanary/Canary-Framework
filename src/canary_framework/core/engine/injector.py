"""Dependency injection engine.

Reads the ``deps`` list from a :class:`ServiceEntry`, looks up each
dependency's runtime instance in the :class:`Registry`, and injects
it onto the target instance as a snake_case attribute.

Attribute name derivation:
    ``DBService``     → ``self.db_service``
    ``UserService``   → ``self.user_service``
    ``HTTPSConn``     → ``self.https_conn``
"""

from __future__ import annotations

import logging

from canary_framework.core.registry.registry import Registry, ServiceEntry
from canary_framework.core.utils.naming import to_snake
from canary_framework.exceptions import DependencyInjectionError

_log = logging.getLogger("cf.di")


def inject_deps(
    instance: object,
    entry: ServiceEntry,
    registry: Registry,
) -> None:
    """Inject declared dependencies onto *instance*.

    For each class in *entry.deps*:
        1. Look up its :class:`ServiceEntry` via the registry.
        2. Convert its class name to snake_case.
        3. ``setattr(instance, attr_name, dependency_instance)``.

    Injection runs before ``on_init`` so the attributes are available
    inside the init hook.

    Args:
        instance: The target service/module instance.
        entry: The :class:`ServiceEntry` describing *instance*.
        registry: The global :class:`Registry`.

    Raises:
        DependencyInjectionError: If a declared dependency has no
            matching entry in the registry.
    """
    for dep_cls in entry.deps:
        dep_entry = registry.get_by_class(dep_cls)
        if dep_entry.instance is None:
            raise DependencyInjectionError(
                f"Cannot inject '{dep_cls.__name__}' into '{entry.name}': "
                f"the dependency instance is None. "
                f"The dependency may not have been initialised yet."
            )
        attr_name = to_snake(dep_cls.__name__)
        setattr(instance, attr_name, dep_entry.instance)
        _log.debug("  %s  →  self.%s", dep_cls.__name__, attr_name)
