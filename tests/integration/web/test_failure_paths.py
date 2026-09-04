"""Integration — the web layer's failure and escape paths.

失败路径与逃生口：校验失败的响应本身不能崩、handler 造好的响应要能原样送出、
非标量参数要从请求体绑定、阻塞 handler 要在装配期就被拒绝。
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, field_validator
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.testclient import TestClient

from canary_framework import Canary
from canary_framework.web import (
    HTTPError,
    RequestValidationError,
    RouteRegistrationError,
    get,
    on_request_error,
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


class BookNotFoundError(Exception):
    """领域异常：仓储层抛出，完全不知道 HTTP 的存在。"""


def test_domain_exception_maps_to_a_status_code() -> None:
    """``@on_request_error`` 把领域异常翻译成响应，业务代码直接抛、不接。"""

    @web_cocoa
    class API:
        @on_request_error(BookNotFoundError)
        async def missing(self, request: Request, exc: Exception) -> Response:
            return JSONResponse({"code": "NOT_FOUND", "message": str(exc)}, status_code=404)

        @get("/books/{isbn}")
        async def detail(self, isbn: str) -> dict:
            raise BookNotFoundError(f"no such book: {isbn}")

    with TestClient(Canary(API)) as client:
        r = client.get("/books/999")

    assert r.status_code == 404
    assert r.json() == {"code": "NOT_FOUND", "message": "no such book: 999"}


def test_handler_lookup_walks_the_mro() -> None:
    """按 ``type(exc).__mro__`` 查找：登记基类即可兜住整族异常。"""

    class RepoError(Exception): ...

    class ConflictError(RepoError): ...

    @web_cocoa
    class API:
        @on_request_error(RepoError)
        async def repo_failed(self, request: Request, exc: Exception) -> Response:
            return JSONResponse({"detail": type(exc).__name__}, status_code=409)

        @get("/conflict")
        async def conflict(self) -> dict:
            raise ConflictError()

    with TestClient(Canary(API)) as client:
        r = client.get("/conflict")

    assert (r.status_code, r.json()) == (409, {"detail": "ConflictError"})


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


def test_builtin_422_can_be_replaced_by_the_house_envelope() -> None:
    """内置映射是可覆盖的——统一错误信封要求 422 也长成自家的样子。"""

    @web_cocoa
    class API:
        @on_request_error(RequestValidationError)
        async def invalid(self, request: Request, exc: Exception) -> Response:
            return JSONResponse({"code": "BAD_REQUEST", "errors": exc.detail}, status_code=400)

        @get("/search")
        async def search(self, keyword: str) -> dict:
            return {"keyword": keyword}

    with TestClient(Canary(API)) as client:
        r = client.get("/search")  # 缺必填 query

    assert r.status_code == 400
    assert r.json()["code"] == "BAD_REQUEST"


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


async def test_duplicate_registration_is_refused_at_assembly() -> None:
    """同一异常类型被登记两次几乎总是 bug，装配期就报出来。"""

    @web_cocoa
    class First:
        @on_request_error(BookNotFoundError)
        async def a(self, request: Request, exc: Exception) -> Response:
            return JSONResponse({}, status_code=404)

        @get("/a")
        async def a_route(self) -> dict:
            return {}

    @web_cocoa(deps=[First])
    class Second:
        @on_request_error(BookNotFoundError)
        async def b(self, request: Request, exc: Exception) -> Response:
            return JSONResponse({}, status_code=410)

        @get("/b")
        async def b_route(self) -> dict:
            return {}

    canary = Canary(Second)
    await canary.init()
    with pytest.raises(RouteRegistrationError, match="duplicate @on_request_error"):
        await canary.start()


def test_blocking_error_handler_is_refused_at_registration() -> None:
    """异常处理器同样跑在请求路径上，同样必须是 async。"""
    with pytest.raises(RouteRegistrationError, match="async"):

        @web_cocoa
        class API:
            @on_request_error(BookNotFoundError)
            def blocking(self, request: Request, exc: Exception) -> Response:
                return JSONResponse({})
