"""Unit tests for the shared type layer — ``State`` and ``LifecycleState``."""

from enum import Enum

import pytest

from canary_framework.common.type import LifecycleState, State

pytestmark = pytest.mark.unit


def test_state_is_an_enum() -> None:
    assert issubclass(State, Enum)


def test_lifecycle_state_inherits_state() -> None:
    assert issubclass(LifecycleState, State)


def test_lifecycle_state_has_eight_string_values() -> None:
    assert len(LifecycleState) == 8
    assert {s.name for s in LifecycleState} == {
        "NEW",
        "INITIALIZING",
        "INITIALIZED",
        "STARTING",
        "STARTED",
        "STOPPING",
        "STOPPED",
        "FAILED",
    }
    assert LifecycleState.NEW.value == "new"
    assert LifecycleState.FAILED.value == "failed"


def test_state_is_extensible_for_new_packages() -> None:
    # 模拟未来扩展包（web / agent）定义自己的状态枚举
    class WebSocketState(State):
        CONNECTING = "connecting"
        OPEN = "open"
        CLOSED = "closed"

    assert issubclass(WebSocketState, State)
    assert not issubclass(WebSocketState, LifecycleState)
    assert WebSocketState.OPEN.value == "open"
