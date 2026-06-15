"""@config decorator — 标记配置类。

将类标记为 Canary Framework 配置类。

@config decorator — marks a config class.
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common import (
    CF_CONFIG_MARKER,
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CanaryConfig,
)


def config() -> Callable[[type], type[CanaryConfig]]:
    """标记一个类为 Canary Framework 配置类。

    配置类必须继承自 CanaryConfig。

    Returns:
        装饰后的类。

    Mark a class as a Canary Framework config class.

    The config class must inherit from CanaryConfig.

    Returns:
        The decorated class.
    """

    def decorator(cls: type) -> type[CanaryConfig]:
        if not issubclass(cls, CanaryConfig):
            raise TypeError(
                f"@config '{cls.__name__}': must inherit from CanaryConfig. "
                f"Did you forget 'class {cls.__name__}(CanaryConfig):'?"
            )
        name = cls.__name__
        setattr(cls, CF_NAME_ATTR, name)
        setattr(cls, CF_CONFIG_MARKER, True)
        setattr(cls, CF_SERVICE_MARKER, True)
        return cls

    return decorator


__all__ = ["config"]
