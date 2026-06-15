"""Unit tests for engine.hooks module."""

import pytest

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook
from canary_framework.core.service._hooks import find_hooks


@pytest.mark.unit
class TestFindHooks:
    """Tests for find_hooks function."""

    def test_find_all_hooks(self) -> None:
        """Test find all hooks on an instance."""

        class TestClass:
            def __init__(self) -> None:
                self.before_startup_called = False
                self.before_shutdown_called = False

            def before_startup(self) -> None:
                self.before_startup_called = True

            def before_shutdown(self) -> None:
                self.before_shutdown_called = True

        setattr(TestClass.before_startup, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], True)
        setattr(TestClass.before_shutdown, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], True)

        instance = TestClass()
        hooks = find_hooks(instance)

        assert isinstance(hooks, dict)
        assert LifecycleHook.BEFORE_STARTUP in hooks
        assert LifecycleHook.BEFORE_SHUTDOWN in hooks
        assert hooks[LifecycleHook.BEFORE_STARTUP] is not None
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is not None

    def test_find_no_hooks(self) -> None:
        """Test find no hooks returns dict with Nones."""

        class TestClass:
            pass

        instance = TestClass()
        hooks = find_hooks(instance)

        assert hooks[LifecycleHook.BEFORE_STARTUP] is None
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is None

    def test_find_partial_hooks(self) -> None:
        """Test find only some hooks."""

        class TestClass:
            pass

        instance = TestClass()
        hooks = find_hooks(instance)

        assert hooks[LifecycleHook.BEFORE_STARTUP] is None
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is None

    def test_inheritance_hooks(self) -> None:
        """Test hooks from parent class are found."""

        class ParentClass:
            pass

        class ChildClass(ParentClass):
            pass

        instance = ChildClass()
        hooks = find_hooks(instance)

        assert hooks[LifecycleHook.BEFORE_STARTUP] is None
