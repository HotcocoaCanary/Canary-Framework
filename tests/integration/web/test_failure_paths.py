"""Integration — the web layer's failure and escape paths.

失败路径与逃生口：校验失败的响应本身不能崩、handler 造好的响应要能原样送出、
非标量参数要从请求体绑定、阻塞 handler 要在装配期就被拒绝。
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, field_validator
from starlette.background import BackgroundTask
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from canary_framework import Canary
from canary_framework.web import (
    HTTPError,
    RouteRegistrationError,
    get,
    post,
    web_cocoa,
)

pytestmark = pytest.mark.integration


class Guarded(BaseModel):
    n: int

    @field_validator("n")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("n must be non-negative")
        return value


def test_validator_error_is_a_serialisable_422() -> None:
    """校验器抛 ValueError 时，422 响应自身必须能被序列化（旧版在此崩成 500）。"""

    @web_cocoa
    class API:
        @post("/guarded")
        async def guarded(self, payload: Guarded) -> dict:
            return {"n": payload.n}

    with TestClient(Canary(API)) as client:
        r = client.post("/guarded", json={"n": -1})

    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail[0]["loc"] == ["n"]
    # ctx 保留下来（约束值有诊断价值），但里面只剩字符串，没有活的异常对象。
    assert detail[0]["ctx"] == {"error": "n must be non-negative"}


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


def test_blocking_handler_is_refused_at_registration() -> None:
    """同步 handler 阻塞的是整个事件循环，不是它自己那个请求——装配期直接拒绝。"""
    with pytest.raises(RouteRegistrationError, match="async"):

        @web_cocoa
        class API:
            @get("/blocking")
            def blocking(self) -> dict:
                return {}


def test_http_error_needs_no_registration() -> None:
    """纯 HTTP 语义的错误直接抛 ``HTTPError``，内置处理器接住，还能带头部。"""

    @web_cocoa
    class API:
        @get("/secret")
        async def secret(self) -> dict:
            raise HTTPError(401, "token expired", headers={"WWW-Authenticate": "Bearer"})

    with TestClient(Canary(API)) as client:
        r = client.get("/secret")

    assert r.status_code == 401
    assert r.json() == {"detail": "token expired"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_unhandled_exception_becomes_a_json_500() -> None:
    """没登记的异常仍是 500，但兜底成 JSON（Starlette 默认是 text/plain）。"""

    @web_cocoa
    class API:
        @get("/boom")
        async def boom(self) -> dict:
            raise RuntimeError("unexpected")

    with TestClient(Canary(API), raise_server_exceptions=False) as client:
        r = client.get("/boom")

    assert r.status_code == 500
    assert r.json() == {"detail": "Internal Server Error"}
