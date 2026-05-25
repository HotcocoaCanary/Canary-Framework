"""Tests for framework exceptions."""

from __future__ import annotations

import pytest

from canary_framework.exceptions import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)


class TestExceptionHierarchy:
    """All framework exceptions should inherit from CanaryFrameworkError."""

    def test_base_class(self) -> None:
        assert issubclass(ConfigurationError, CanaryFrameworkError)
        assert issubclass(ServiceNotFoundError, CanaryFrameworkError)
        assert issubclass(CircularDependencyError, CanaryFrameworkError)
        assert issubclass(DependencyInjectionError, CanaryFrameworkError)
        assert issubclass(LifecycleHookError, CanaryFrameworkError)
        assert issubclass(CanaryFrameworkError, Exception)

    def test_catch_all_framework_errors(self) -> None:
        """All framework errors should be catchable via the base class."""
        for exc_cls in [
            ConfigurationError,
            ServiceNotFoundError,
            CircularDependencyError,
            DependencyInjectionError,
            LifecycleHookError,
        ]:
            with pytest.raises(CanaryFrameworkError):
                raise exc_cls("test")

    def test_error_messages_are_preserved(self) -> None:
        msg = "Something went wrong in the config layer"
        exc = ConfigurationError(msg)
        assert str(exc) == msg

    def test_error_chaining(self) -> None:
        original = ValueError("original error")
        wrapped = DependencyInjectionError("wrapped")
        wrapped.__cause__ = original
        assert wrapped.__cause__ is original
