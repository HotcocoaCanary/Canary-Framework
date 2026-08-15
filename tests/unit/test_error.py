"""Unit tests for the shared error layer — ``CanaryError`` and its subclasses."""

import pytest

from canary_framework.common.error import (
    CanaryError,
    CircularDependencyError,
    LifecycleError,
)

pytestmark = pytest.mark.unit


def test_all_errors_inherit_canary_error() -> None:
    assert issubclass(CircularDependencyError, CanaryError)
    assert issubclass(LifecycleError, CanaryError)


def test_canary_error_is_a_standard_exception() -> None:
    assert issubclass(CanaryError, Exception)


def test_canary_error_catches_every_specific_error() -> None:
    with pytest.raises(CanaryError):
        raise LifecycleError()


def test_circular_dependency_error_carries_the_cycle() -> None:
    err = CircularDependencyError(["A", "B", "A"])
    assert err.cycle == ["A", "B", "A"]
    assert "A -> B -> A" in str(err)


def test_error_is_extensible_for_new_packages() -> None:
    class WebError(CanaryError):
        pass

    class RouteNotFoundError(WebError):
        pass

    assert issubclass(WebError, CanaryError)
    assert issubclass(RouteNotFoundError, CanaryError)
    with pytest.raises(CanaryError):
        raise RouteNotFoundError()
