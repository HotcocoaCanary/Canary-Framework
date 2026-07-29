"""Unit tests for framework exception contracts."""

import pytest

from canary_framework.common.errors import (
    ApplicationNotInitializedError,
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyDirectionError,
    DependencyInjectionError,
    LifecycleHookError,
    LifecycleStateError,
    RouteCompilationError,
    ServiceNotFoundError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "error_type",
    [
        ApplicationNotInitializedError,
        LifecycleStateError,
        DependencyDirectionError,
        RouteCompilationError,
    ],
)
def test_new_errors_share_framework_base(error_type: type[Exception]) -> None:
    assert issubclass(error_type, CanaryFrameworkError)


@pytest.mark.unit
def test_dependency_direction_error_is_dependency_error() -> None:
    assert issubclass(DependencyDirectionError, DependencyInjectionError)


@pytest.mark.unit
def test_existing_errors_remain_framework_errors() -> None:
    for error_type in (
        ConfigurationError,
        ServiceNotFoundError,
        CircularDependencyError,
        DependencyInjectionError,
        LifecycleHookError,
    ):
        assert issubclass(error_type, CanaryFrameworkError)


@pytest.mark.unit
def test_framework_errors_preserve_messages() -> None:
    for error_type in (
        CanaryFrameworkError,
        ApplicationNotInitializedError,
        LifecycleStateError,
        DependencyDirectionError,
        RouteCompilationError,
    ):
        assert str(error_type("contract failure")) == "contract failure"
