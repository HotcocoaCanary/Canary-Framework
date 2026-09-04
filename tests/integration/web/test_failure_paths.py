"""Integration — the web layer's failure and escape paths.

请求路径上的失败与逃生口。
"""

from __future__ import annotations

import pytest

from canary_framework.web import RouteRegistrationError, get, web_cocoa

pytestmark = pytest.mark.integration


def test_blocking_handler_is_refused_at_registration() -> None:
    """同步 handler 阻塞的是整个事件循环，不是它自己那个请求——装配期直接拒绝。"""
    with pytest.raises(RouteRegistrationError, match="async"):

        @web_cocoa
        class API:
            @get("/blocking")
            def blocking(self) -> dict:
                return {}
