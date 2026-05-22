from __future__ import annotations

from cf.core.utils.naming import to_snake
from cf.core.registry.registry import Registry


def inject_deps(
    instance: object, entry, registry: Registry
) -> None:
    for dep_cls in entry.deps:
        dep_entry = registry.get_by_class(dep_cls)
        attr_name = to_snake(dep_cls.__name__)
        setattr(instance, attr_name, dep_entry.instance)
