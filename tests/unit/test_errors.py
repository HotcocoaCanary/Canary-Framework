"""Unit tests for common.errors module."""

import pytest

from canary_framework.common.errors import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    ServiceNotFoundError,
)


@pytest.mark.unit
class TestExceptions:
    """Tests for exception classes."""

    def test_canary_framework_error_inheritance(self) -> None:
        """Test that all exceptions inherit from CanaryFrameworkError."""
        assert issubclass(ConfigurationError, CanaryFrameworkError)
        assert issubclass(ServiceNotFoundError, CanaryFrameworkError)
        assert issubclass(CircularDependencyError, CanaryFrameworkError)
        assert issubclass(DependencyInjectionError, CanaryFrameworkError)

    def test_exception_instantiation(self) -> None:
        """Test that exceptions can be instantiated with messages."""
        error = CanaryFrameworkError("Test error")
        assert str(error) == "Test error"

        config_error = ConfigurationError("Config failed")
        assert str(config_error) == "Config failed"

        not_found_error = ServiceNotFoundError("Service not found")
        assert str(not_found_error) == "Service not found"

        circular_error = CircularDependencyError("Cycle detected")
        assert str(circular_error) == "Cycle detected"

        di_error = DependencyInjectionError("DI failed")
        assert str(di_error) == "DI failed"

    def test_exception_catch(self) -> None:
        """Test that specific exceptions can be caught by base class."""
        try:
            raise ConfigurationError("Test")
        except CanaryFrameworkError:
            assert True
