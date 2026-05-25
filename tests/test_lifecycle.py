"""Tests for :mod:`canary_framework.core.decorators.lifecycle`."""

from __future__ import annotations

from canary_framework.core.decorators.lifecycle import (
    LifecycleHook,
    find_hooks,
    on_end,
    on_init,
    on_start,
)


class TestLifecycleHookEnum:
    """Verify the StrEnum values match hook names used by the engine."""

    def test_values_are_strings(self) -> None:
        assert LifecycleHook.INIT == "on_init"  # type: ignore[comparison-overlap]
        assert LifecycleHook.START == "on_start"  # type: ignore[comparison-overlap]
        assert LifecycleHook.END == "on_end"  # type: ignore[comparison-overlap]

    def test_iteration(self) -> None:
        names = list(LifecycleHook)
        assert len(names) == 3
        assert LifecycleHook.INIT in names


class TestFindHooks:
    """Unit tests for hook discovery on service instances."""

    def test_all_hooks_decorated(self) -> None:
        class MyService:
            @on_init
            def init(self, ctx: object) -> None:
                pass

            @on_start
            def start(self) -> None:
                pass

            @on_end
            def stop(self) -> None:
                pass

        inst = MyService()
        hooks = find_hooks(inst)

        assert hooks[LifecycleHook.INIT] is not None
        assert hooks[LifecycleHook.START] is not None
        assert hooks[LifecycleHook.END] is not None

    def test_no_hooks(self) -> None:
        class Empty:
            pass

        hooks = find_hooks(Empty())
        assert hooks[LifecycleHook.INIT] is None
        assert hooks[LifecycleHook.START] is None
        assert hooks[LifecycleHook.END] is None

    def test_no_fallback_by_name(self) -> None:
        """Methods named on_init/on_start/on_end but NOT decorated
        must NOT be found (no implicit fallback)."""

        class Accidental:
            def on_init(self, ctx: object) -> None:
                pass

            def on_start(self) -> None:
                pass

        hooks = find_hooks(Accidental())
        assert hooks[LifecycleHook.INIT] is None, (
            "on_init without @on_init decorator must not be detected"
        )
        assert hooks[LifecycleHook.START] is None, (
            "on_start without @on_start decorator must not be detected"
        )

    def test_partial_hooks(self) -> None:
        """Only decorated hooks should be found."""

        class Partial:
            @on_start
            def start(self) -> None:
                pass

            def on_init(self, ctx: object) -> None:
                pass

        hooks = find_hooks(Partial())
        assert hooks[LifecycleHook.INIT] is None
        assert hooks[LifecycleHook.START] is not None
        assert hooks[LifecycleHook.END] is None

    def test_decorator_preserves_callable(self) -> None:
        """The decorator must return the same function (for introspection)."""

        @on_init
        def my_init(self, ctx: object) -> None:  # type: ignore[no-untyped-def]
            pass

        assert callable(my_init)
        assert my_init.__name__ == "my_init"

    def test_hooks_cacheable_result(self) -> None:
        """find_hooks returns a dict with all three keys, some maybe None."""

        class Svc:
            @on_init
            def init(self, ctx: object) -> None:
                pass

        hooks = find_hooks(Svc())
        assert set(hooks.keys()) == {
            LifecycleHook.INIT,
            LifecycleHook.START,
            LifecycleHook.END,
        }
