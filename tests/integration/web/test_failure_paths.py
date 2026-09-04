"""Integration — the web layer's failure and escape paths.

请求路径上的失败与逃生口。
"""

from __future__ import annotations

import pytest
from starlette.background import BackgroundTask
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from canary_framework import Canary
from canary_framework.web import RouteRegistrationError, get, post, web_cocoa

pytestmark = pytest.mark.integration


def test_blocking_handler_is_refused_at_registration() -> None:
    """同步 handler 阻塞的是整个事件循环，不是它自己那个请求——装配期直接拒绝。"""
    with pytest.raises(RouteRegistrationError, match="async"):

        @web_cocoa
        class API:
            @get("/blocking")
            def blocking(self) -> dict:
                return {}


def test_handler_may_return_a_response_object() -> None:
    """handler 造好的响应原样放行——自定义状态码 / 媒体类型 / 头部。"""

    @web_cocoa
    class API:
        @get("/plain")
        async def plain(self) -> PlainTextResponse:
            return PlainTextResponse("hello", status_code=201, headers={"x-kind": "raw"})

    with TestClient(Canary(API)) as client:
        r = client.get("/plain")

    assert (r.status_code, r.text, r.headers["x-kind"]) == (201, "hello", "raw")


def test_background_task_rides_along_on_the_returned_response() -> None:
    """后台任务不需要框架另开机制：挂在返回的响应上即可。"""
    done: list[str] = []

    @web_cocoa
    class API:
        @get("/accept")
        async def accept(self) -> PlainTextResponse:
            return PlainTextResponse(
                "accepted",
                status_code=202,
                background=BackgroundTask(done.append, "ran"),
            )

    with TestClient(Canary(API)) as client:
        r = client.get("/accept")

    assert r.status_code == 202
    assert done == ["ran"]  # TestClient 会等后台任务跑完


def test_non_scalar_parameters_bind_from_the_body() -> None:
    """推断规则：标量走 query，其余走 body——``dict`` 不再被误当查询参数。"""

    @web_cocoa
    class API:
        @post("/raw")
        async def raw(self, item: dict, tag: str = "none") -> dict:
            return {"item": item, "tag": tag}

    with TestClient(Canary(API)) as client:
        r = client.post("/raw?tag=x", json={"a": 1})

    assert r.json() == {"item": {"a": 1}, "tag": "x"}
