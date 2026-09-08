"""Integration — the runtime tells you what it assembled.

装配摘要：框架掌握着全部事实，却一直零输出。DEBUG 级别一次说清楚。
"""

from __future__ import annotations

import logging

import pytest

from canary_framework import Canary, cocoa

pytestmark = pytest.mark.integration


@cocoa
class Database:
    pass


@cocoa(deps=[Database])
class Repository:
    pass


@cocoa(deps=[Repository])
class App:
    pass


async def test_assembly_summary_is_logged_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="canary.runtime"):
        async with Canary(App):
            pass

    summary = "\n".join(r.getMessage() for r in caplog.records)
    assert "Canary assembled 3 unit(s)" in summary
    assert "1. Database" in summary
    assert "3. App  <- Repository" in summary


async def test_multiple_roots_are_told_they_have_no_after_all_position(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """多根时没有单元最后启动，因此没有 after-all 位置——这一点要说出来。"""

    @cocoa
    class First:
        pass

    @cocoa
    class Second:
        pass

    with caplog.at_level(logging.DEBUG, logger="canary.runtime"):
        async with Canary(First, Second):
            pass

    summary = "\n".join(r.getMessage() for r in caplog.records)
    assert "after everything started" in summary
