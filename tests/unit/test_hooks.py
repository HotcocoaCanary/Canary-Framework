"""Unit tests for engine.hooks module."""

import pytest

from canary_framework.common import CF_HOOK_MARKER_MAP, LifecycleHook
from canary_framework.engine.hooks import find_hooks


@pytest.mark.unit
class TestFindHooks:
    """Tests for find_hooks function."""

    def test_find_all_hooks(self) -> None:
        """Test find all hooks on an instance."""

        class TestClass:
            def __init__(self) -> None:
                self.after_config_called = False
                self.after_init_called = False
                self.before_startup_called = False
                self.before_shutdown_called = False

            def after_config(self) -> None:
                self.after_config_called = True

            def after_init(self) -> None:
                self.after_init_called = True

            def before_startup(self) -> None:
                self.before_startup_called = True

            def before_shutdown(self) -> None:
                self.before_shutdown_called = True

        # Add markers
        setattr(TestClass.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)
        setattr(TestClass.after_init, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_INIT], True)
        setattr(TestClass.before_startup, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_STARTUP], True)
        setattr(TestClass.before_shutdown, CF_HOOK_MARKER_MAP[LifecycleHook.BEFORE_SHUTDOWN], True)

        instance = TestClass()
        hooks = find_hooks(instance)

        assert isinstance(hooks, dict)
        assert LifecycleHook.AFTER_CONFIG in hooks
        assert LifecycleHook.AFTER_INIT in hooks
        assert LifecycleHook.BEFORE_STARTUP in hooks
        assert LifecycleHook.BEFORE_SHUTDOWN in hooks
        assert callable(hooks[LifecycleHook.AFTER_CONFIG])
        assert callable(hooks[LifecycleHook.AFTER_INIT])
        assert callable(hooks[LifecycleHook.BEFORE_STARTUP])
        assert callable(hooks[LifecycleHook.BEFORE_SHUTDOWN])

    def test_find_no_hooks(self) -> None:
        """Test find no hooks returns dict with Nones."""

        class TestClass:
            pass

        instance = TestClass()
        hooks = find_hooks(instance)

        assert hooks[LifecycleHook.AFTER_CONFIG] is None
        assert hooks[LifecycleHook.AFTER_INIT] is None
        assert hooks[LifecycleHook.BEFORE_STARTUP] is None
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is None

    def test_find_partial_hooks(self) -> None:
        """Test find only some hooks."""

        class TestClass:
            def after_config(self) -> None:
                pass

        setattr(TestClass.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)

        instance = TestClass()
        hooks = find_hooks(instance)

        assert callable(hooks[LifecycleHook.AFTER_CONFIG])
        assert hooks[LifecycleHook.AFTER_INIT] is None
        assert hooks[LifecycleHook.BEFORE_STARTUP] is None
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is None

    def test_inheritance_hooks(self) -> None:
        """Test hooks from parent class are found."""

        class ParentClass:
            def after_config(self) -> None:
                pass

        setattr(ParentClass.after_config, CF_HOOK_MARKER_MAP[LifecycleHook.AFTER_CONFIG], True)

        class ChildClass(ParentClass):
            pass

        instance = ChildClass()
        hooks = find_hooks(instance)

        assert callable(hooks[LifecycleHook.AFTER_CONFIG])
