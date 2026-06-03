"""Engine utilities — helper functions for the framework engine."""

from __future__ import annotations

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ServiceMeta,
)


def make_subclass(
    cls: type,
    base: type,
    meta: ServiceMeta,
    name: str,
    *,
    extra_marker: str | None = None,
) -> type:
    """Dynamically create a subclass that inherits from both the original class and the base.

    This function is used by decorators to inject base classes into decorated classes
    while preserving metadata and module information.

    Args:
        cls: The original class to wrap.
        base: The base class to inject.
        meta: Service metadata to attach to the new class.
        name: The service name.
        extra_marker: Optional additional marker attribute to set.

    Returns:
        A new class that inherits from both base and cls.
    """
    new_cls = type(cls.__name__, (base, cls), {})
    new_cls.__module__ = cls.__module__
    new_cls.__qualname__ = cls.__qualname__
    setattr(new_cls, CF_SERVICE_MARKER, True)
    setattr(new_cls, CF_SERVICE_META, meta)
    setattr(new_cls, CF_NAME_ATTR, name)
    if extra_marker is not None:
        setattr(new_cls, extra_marker, True)

    if meta.deps:
        from canary_framework.engine.injector import to_snake

        annotations = dict(getattr(cls, "__annotations__", {}))
        for dep_cls in meta.deps:
            attr_name = to_snake(dep_cls.__name__)
            if attr_name not in annotations:
                annotations[attr_name] = dep_cls

        if annotations:
            new_cls.__annotations__ = annotations

    return new_cls


__all__ = ["make_subclass"]
