"""Configuration decorator — converts plain classes to pydantic-settings models.

The ``@config`` decorator transforms a regular Python class into a
:class:`pydantic_settings.BaseSettings` subclass.  The resulting class
automatically reads environment variables and ``.env`` files.

Priority (highest first):
    1. Environment variable (e.g. ``export HOST=...``)
    2. ``.env`` file in the current working directory
    3. Default value declared in the class body
"""

from __future__ import annotations

from typing import TypeVar

from pydantic_settings import BaseSettings, SettingsConfigDict

_C = TypeVar("_C", bound=type)


def config(cls: _C) -> type:  # noqa: UP047
    """Convert a plain class into a :class:`~pydantic_settings.BaseSettings` subclass.

    The decorator creates a new class dynamically via :func:`type()`:

    1. Copies ``__annotations__`` so pydantic recognises the fields.
    2. Copies class-level variables as default values.
    3. Applies :class:`~pydantic_settings.SettingsConfigDict` with
       ``env_file=".env"``, ``extra="ignore"``, and no prefix — field
       names map directly to environment variable names.
    4. Preserves the original class's ``__name__``, ``__qualname__``,
       and ``__module__`` for debugging.

    The decorator can be used bare (``@config``) or with parentheses
    (``@config()``) — both are equivalent.

    Args:
        cls: A class with type-annotated fields and optional defaults.

    Returns:
        A new class that inherits from :class:`BaseSettings` and behaves
        identically to the original class plus environment-variable loading.

    Example::

        @config
        class AppConfig:
            host: str = "0.0.0.0"
            port: int = 8000

        cfg = AppConfig()       # reads HOST, PORT env vars and .env
        assert cfg.host == "…"  # typed, validated by pydantic

    .. note::

        The ``.env`` file path is hard-coded to ``"env_file=.env"``
        (relative to the current working directory).  For services that
        need a custom path, consider overriding via
        :attr:`model_config <pydantic_settings.BaseSettings.model_config>`.
    """
    annotations = getattr(cls, "__annotations__", {})

    base: type = type(
        cls.__name__,
        (BaseSettings,),
        {
            "__annotations__": annotations,
            "model_config": SettingsConfigDict(
                env_file=".env",
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

    base.__name__ = cls.__name__
    base.__qualname__ = cls.__qualname__
    base.__module__ = cls.__module__

    return base
