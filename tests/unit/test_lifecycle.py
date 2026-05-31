"""Unit tests for lifecycle hook decorators."""

from __future__ import annotations

from canary_framework.common import LifecycleHook
from canary_framework.decorators import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
)
from canary_framework.engine import find_hooks


class TestLifecycleDecorators:
    def test_after_config_sets_marker(self) -> None:
        class Svc:
            @after_config
            def setup(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert hooks[LifecycleHook.AFTER_CONFIG] is not None

    def test_after_init_sets_marker(self) -> None:
        class Svc:
            @after_init
            def init(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert hooks[LifecycleHook.AFTER_INIT] is not None

    def test_before_startup_sets_marker(self) -> None:
        class Svc:
            @before_startup
            def start(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert hooks[LifecycleHook.BEFORE_STARTUP] is not None

    def test_before_shutdown_sets_marker(self) -> None:
        class Svc:
            @before_shutdown
            def stop(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert hooks[LifecycleHook.BEFORE_SHUTDOWN] is not None

    def test_all_hooks_discovered(self) -> None:
        class Svc:
            @after_config
            def on_cfg(self) -> None:
                pass

            @after_init
            def on_it(self) -> None:
                pass

            @before_startup
            def on_s(self) -> None:
                pass

            @before_shutdown
            def on_e(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert all(v is not None for v in hooks.values())

    def test_find_hooks_with_no_hooks(self) -> None:
        class Svc:
            def regular(self) -> None:
                pass

        hooks = find_hooks(Svc())
        assert all(v is None for v in hooks.values())

    def test_find_hooks_with_inheritance(self) -> None:
        class Base:
            @after_init
            def base_init(self) -> None:
                pass

        class Child(Base):
            @before_startup
            def child_start(self) -> None:
                pass

        hooks = find_hooks(Child())
        assert hooks[LifecycleHook.AFTER_INIT] is not None
        assert hooks[LifecycleHook.BEFORE_STARTUP] is not None
