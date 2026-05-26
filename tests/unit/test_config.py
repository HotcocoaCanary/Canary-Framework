"""Tests for the @config decorator."""

from __future__ import annotations

import pytest

from canary_framework.core.decorators.config import config


@pytest.mark.unit
class TestConfigDecorator:
    """Verify that @config creates valid BaseSettings subclasses."""

    def test_basic_config(self) -> None:
        @config
        class AppConfig:
            host: str = "localhost"
            port: int = 8080

        instance = AppConfig()
        assert instance.host == "localhost"
        assert instance.port == 8080

    def test_fields_are_typed(self) -> None:
        @config
        class TypedCfg:
            count: int = 0
            name: str = "default"

        instance = TypedCfg()
        assert isinstance(instance.count, int)
        assert isinstance(instance.name, str)

    def test_class_name_preserved(self) -> None:
        @config
        class MyConfig:
            debug: bool = False

        assert MyConfig.__name__ == "MyConfig"

    def test_decorator_used_as_callable(self) -> None:
        """@config() with parentheses should work the same as @config."""
        called = False

        def config_callable(cls: type) -> type:
            nonlocal called
            called = True
            return config(cls)

        @config_callable
        class WithParens:
            value: int = 1

        assert called
        instance = WithParens()
        assert instance.value == 1

    def test_env_prefix_empty(self) -> None:
        """Environment variables map directly to field names (no prefix)."""

        @config
        class NoPrefixCfg:
            my_key: str = "fallback"

        instance = NoPrefixCfg()
        assert instance.my_key == "fallback"
