"""Unit tests for exception classes."""

from __future__ import annotations

import pytest

from canary_framework.common import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)


class TestExceptions:
    def test_canary_framework_error_is_exception(self) -> None:
        assert issubclass(CanaryFrameworkError, Exception)

    def test_error_hierarchy(self) -> None:
        for cls in (
            ConfigurationError,
            ServiceNotFoundError,
            CircularDependencyError,
            DependencyInjectionError,
            LifecycleHookError,
        ):
            assert issubclass(cls, CanaryFrameworkError)

    def test_catch_all_with_base(self) -> None:
        try:
            raise ConfigurationError("test")
        except CanaryFrameworkError:
            pass
        else:
            pytest.fail("Should have been caught by CanaryFrameworkError")
