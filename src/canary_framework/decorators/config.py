"""Configuration declaration decorator."""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import CF_NAME_ATTR, CanaryConfig


def config() -> Callable[[type], type[CanaryConfig]]:
    """Mark a CanaryConfig subclass and return it unchanged."""

    def decorator(cls: type) -> type[CanaryConfig]:
        if not issubclass(cls, CanaryConfig):
            raise TypeError(
                f"@config '{cls.__name__}': must inherit from CanaryConfig. "
                f"Did you forget 'class {cls.__name__}(CanaryConfig):'?"
            )
        name = cls.__name__
        setattr(cls, CF_NAME_ATTR, name)
        return cls

    return decorator


__all__ = ["config"]
