"""Framework-specific exceptions.

All Canary Framework errors inherit from :class:`CanaryFrameworkError`,
allowing callers to catch framework errors specifically while letting
unrelated exceptions propagate normally.

Hierarchy::

    CanaryFrameworkError
    ├── ConfigurationError
    ├── ServiceNotFoundError
    ├── CircularDependencyError
    ├── DependencyInjectionError
    └── LifecycleHookError
"""

from __future__ import annotations


class CanaryFrameworkError(Exception):
    """Base class for all exceptions raised by Canary Framework.

    Catch this to handle any framework-originated error while allowing
    system-level and third-party exceptions to pass through.
    """


class ConfigurationError(CanaryFrameworkError):
    """Raised when configuration loading or validation fails.

    Examples:
        - ``@config`` class lacks required annotations
        - Config instance not found when ``Context.get_config()`` fails
        - Pydantic validation error during ``BaseSettings`` construction
    """


class ServiceNotFoundError(CanaryFrameworkError):
    """Raised when a requested service or module cannot be located.

    Examples:
        - ``Registry.get_by_name(name)`` called with an unregistered name
        - ``Context.resolve(cls)`` called for a service not in the module tree
        - Dependency declared via ``deps=[]`` points to an unknown service
    """


class CircularDependencyError(CanaryFrameworkError):
    """Raised when the topological sort detects a cycle in the dependency graph.

    The error message includes the names of the services that form the cycle.
    """


class DependencyInjectionError(CanaryFrameworkError):
    """Raised when dependency injection fails at runtime.

    Examples:
        - A ``deps=[]`` entry is not a ``@service`` or ``@module`` class
        - Attempting to inject a service whose instance has not been created
        - Type mismatch between declared dependency and resolved instance
    """


class LifecycleHookError(CanaryFrameworkError):
    """Raised when a lifecycle hook raises an unhandled exception.

    The framework calls ``on_init`` / ``on_start`` / ``on_end`` hooks
    automatically.  If a hook raises, the error is wrapped in this type
    so callers can distinguish between hook failures and framework bugs.
    """
