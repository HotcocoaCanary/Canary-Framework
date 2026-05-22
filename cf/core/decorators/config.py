from __future__ import annotations

from typing import Callable

from pydantic_settings import BaseSettings, SettingsConfigDict


def config(cls: type | None = None) -> Callable[..., type] | type:
    if cls is None:
        return lambda c: _apply_config(c)

    return _apply_config(cls)


def _apply_config(cls: type) -> type:
    annotations = getattr(cls, "__annotations__", {})
    bases = (BaseSettings,)

    settings_cls = type(
        cls.__name__,
        bases,
        {
            "__annotations__": annotations,
            "model_config": SettingsConfigDict(
                env_file=None,
                env_file_encoding="utf-8",
                extra="ignore",
                env_prefix="",
            ),
            **{
                k: v
                for k, v in vars(cls).items()
                if not k.startswith("__") and k != "__annotations__"
            },
        },
    )
    settings_cls.__name__ = cls.__name__
    settings_cls.__qualname__ = cls.__qualname__
    settings_cls.__module__ = cls.__module__
    return settings_cls
