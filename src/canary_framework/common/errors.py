"""Framework-specific exception hierarchy."""

from __future__ import annotations


class CanaryFrameworkError(Exception):
    """Base class for framework errors."""


class ApplicationNotInitializedError(CanaryFrameworkError):
    """Raised when a runtime root is used before explicit initialization."""


class LifecycleStateError(CanaryFrameworkError):
    """Raised for an invalid lifecycle state transition."""


class ConfigurationError(CanaryFrameworkError):
    """Raised for invalid application configuration."""


class ServiceNotFoundError(CanaryFrameworkError):
    """Raised when a requested service is absent."""


class CircularDependencyError(CanaryFrameworkError):
    """Raised when dependency resolution finds a cycle."""


class DependencyInjectionError(CanaryFrameworkError):
    """Raised when dependency wiring fails."""


class DependencyDirectionError(DependencyInjectionError):
    """Raised when a dependency violates node-layer rules."""


class LifecycleHookError(CanaryFrameworkError):
    """Raised when a lifecycle hook is invalid or fails."""


class RouteCompilationError(CanaryFrameworkError):
    """Raised when routes cannot be compiled."""


__all__ = [
    "ApplicationNotInitializedError",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyDirectionError",
    "DependencyInjectionError",
    "LifecycleHookError",
    "LifecycleStateError",
    "RouteCompilationError",
    "ServiceNotFoundError",
]
