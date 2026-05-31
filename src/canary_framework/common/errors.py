"""Framework-specific exception classes.

All errors inherit from :class:`CanaryFrameworkError`, so callers can
catch a single type to handle any framework error.
"""

from __future__ import annotations


class CanaryFrameworkError(Exception):
    """Base class for all Canary Framework errors."""


class ConfigurationError(CanaryFrameworkError):
    """Raised when configuration loading or validation fails."""


class ServiceNotFoundError(CanaryFrameworkError):
    """Raised when a requested service or module cannot be located."""


class CircularDependencyError(CanaryFrameworkError):
    """Raised when the topological sort detects a cycle."""


class DependencyInjectionError(CanaryFrameworkError):
    """Raised when dependency injection fails at runtime."""


class LifecycleHookError(CanaryFrameworkError):
    """Raised when a runtime hook raises an unhandled exception."""


__all__ = [
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHookError",
    "ServiceNotFoundError",
]
