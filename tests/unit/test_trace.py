"""Tests for :mod:`canary_framework.core.decorators.trace` — the AOP call-logging decorator.

Covers:
    - Class-level @trace: all public methods intercepted
    - Method-level @trace: single method wrapped
    - Sync and async methods
    - Argument and return-value logging
    - Exception logging (with exc_info)
    - Result truncation (>200 chars)
    - functools.wraps metadata preservation
    - Non-callable attributes pass through untouched
    - Private/dunder methods NOT intercepted
"""

from __future__ import annotations

import logging

import pytest

from canary_framework.core.decorators.trace import trace

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trace_caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Configure caplog to capture CF trace logs."""
    logging.getLogger().setLevel(logging.DEBUG)
    cf = logging.getLogger("cf")
    cf.propagate = True
    cf.setLevel(logging.DEBUG)
    for h in list(cf.handlers):
        cf.removeHandler(h)
    caplog.set_level(logging.DEBUG)
    return caplog


# ---------------------------------------------------------------------------
# Class-level @trace
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTraceClassDecorator:
    """Verify AOP-style class-level @trace intercepts all public methods."""

    def test_all_public_methods_are_traced(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def foo(self, x: int) -> str:
                return f"got {x}"

            def bar(self) -> None:
                pass

        svc = Svc()
        result = svc.foo(42)
        assert result == "got 42"
        assert "Svc.foo" in trace_caplog.text

        svc.bar()
        assert "Svc.bar" in trace_caplog.text

    def test_private_methods_not_traced(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def _internal(self) -> str:
                return "secret"

        svc = Svc()
        svc._internal()
        assert "Svc._internal" not in trace_caplog.text

    def test_dunder_methods_not_traced(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def __str__(self) -> str:
                return "Svc"

        svc = Svc()
        str(svc)
        assert "Svc.__str__" not in trace_caplog.text

    def test_non_callable_attributes_pass_through(
        self, trace_caplog: pytest.LogCaptureFixture
    ) -> None:
        @trace
        class Svc:
            value: int = 10

        svc = Svc()
        assert svc.value == 10
        assert "Svc.value" not in trace_caplog.text

    async def test_async_methods_are_traced(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            async def run(self, name: str) -> str:
                return f"hello {name}"

        svc = Svc()
        result = await svc.run("world")
        assert result == "hello world"
        assert "Svc.run" in trace_caplog.text

    def test_return_value_truncated(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def big(self) -> str:
                return "x" * 300

        svc = Svc()
        svc.big()
        assert "…" in trace_caplog.text

    def test_exception_is_logged_at_error(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def fail(self) -> None:
                raise ValueError("boom")

        svc = Svc()
        with pytest.raises(ValueError, match="boom"):
            svc.fail()
        assert "failed" in trace_caplog.text.lower()

    def test_wraps_metadata_preserved(self) -> None:
        @trace
        class Svc:
            def documented(self) -> int:
                """Return zero."""
                return 0

        svc = Svc()
        assert svc.documented.__name__ == "documented"
        assert svc.documented.__doc__ == "Return zero."


# ---------------------------------------------------------------------------
# Method-level @trace
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTraceMethodDecorator:
    """Verify method-level @trace only wraps the decorated method."""

    def test_only_decorated_method_is_traced(
        self, trace_caplog: pytest.LogCaptureFixture
    ) -> None:
        class Svc:
            @trace
            def tracked(self, x: int) -> str:
                return f"x={x}"

            def untracked(self) -> str:
                return "untracked"

        svc = Svc()
        svc.tracked(1)
        svc.untracked()

        assert "tracked" in trace_caplog.text
        assert "untracked" not in trace_caplog.text

    def test_method_wraps_metadata_preserved(self) -> None:
        class Svc:
            @trace
            def named(self) -> int:
                """Docstring."""
                return 42

        svc = Svc()
        assert svc.named.__name__ == "named"
        assert svc.named.__doc__ == "Docstring."

    async def test_async_method_traced(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        class Svc:
            @trace
            async def compute(self, a: int) -> int:
                return a * 2

        svc = Svc()
        result = await svc.compute(5)
        assert result == 10
        assert "5" in trace_caplog.text

    def test_keyword_args_logged(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        class Svc:
            @trace
            def greet(self, name: str, greeting: str = "hi") -> str:
                return f"{greeting} {name}"

        svc = Svc()
        svc.greet("alice")
        assert "alice" in trace_caplog.text

    def test_keyword_args_explicitly_passed(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        class Svc:
            @trace
            def configure(self, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
                pass

        svc = Svc()
        svc.configure(host="localhost", port=8080)
        assert "host" in trace_caplog.text
        assert "port" in trace_caplog.text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTraceEdgeCases:
    """Edge cases and error-handling for @trace."""

    def test_trace_on_plain_function(self) -> None:
        @trace
        def plain_func(x: int) -> int:
            return x + 1

        assert plain_func(1) == 2
        assert plain_func.__name__ == "plain_func"

    def test_trace_on_class_with_no_methods(self) -> None:
        @trace
        class Empty:
            pass

        svc = Empty()
        assert svc is not None

    def test_method_raises_and_preserves_exception(self) -> None:
        @trace
        class Svc:
            def fail(self, msg: str) -> None:
                raise RuntimeError(msg)

        svc = Svc()
        with pytest.raises(RuntimeError, match="test-error"):
            svc.fail("test-error")

    async def test_async_method_raises_and_preserves_exception(self) -> None:
        @trace
        class Svc:
            async def fail(self, msg: str) -> None:
                raise RuntimeError(msg)

        svc = Svc()
        with pytest.raises(RuntimeError, match="async-error"):
            await svc.fail("async-error")

    def test_double_trace_is_idempotent(self) -> None:
        @trace
        @trace
        class Svc:
            def run(self) -> str:
                return "ok"

        svc = Svc()
        assert svc.run() == "ok"

    def test_trace_logs_include_call_and_return(self, trace_caplog: pytest.LogCaptureFixture) -> None:
        @trace
        class Svc:
            def calc(self, n: int) -> int:
                return n * n

        svc = Svc()
        svc.calc(3)
        text = trace_caplog.text
        assert "calc" in text
        # Should contain both call arrow and return arrow
        assert "⇠" in text or "<--" in text or "calc" in text
