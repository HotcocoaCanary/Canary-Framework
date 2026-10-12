"""Web 应用单元：从请求到响应的整条路。"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import httpx
import pytest
from pydantic import BaseModel

from canary_framework import Canary, DeclarationError, LifecycleError, dep, init, start, stop
from canary_framework.test import running, unit
from canary_framework.web.asgi import Application
from canary_framework.web.asgi.app import (
    App,
    HTTPError,
    Request,
    Response,
    Router,
    delete,
    error,
    get,
    post,
    put,
)
from canary_framework.web.asgi.server import Server

pytestmark = pytest.mark.functional


class Reader(BaseModel):
    id: int
    name: str
    joined: datetime.date | None = None


class NewReader(BaseModel):
    name: str


class ReaderNotFoundError(Exception):
    def __init__(self, reader_id: int) -> None:
        self.reader_id = reader_id


class Readers(Canary):
    @init
    def seed(self) -> None:
        self.rows = {7: Reader(id=7, name="七")}

    def get(self, reader_id: int) -> Reader:
        if reader_id not in self.rows:
            raise ReaderNotFoundError(reader_id)
        return self.rows[reader_id]


class ReaderApi(Router, prefix="/readers"):
    readers = dep(Readers)

    @get
    async def search(self, keyword: str | None = None, tag: list[int] = [], limit: int = 20) -> Any:  # noqa: B006
        return {"keyword": keyword, "tag": tag, "limit": limit}

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return self.readers.get(reader_id)

    @post(status=201)
    async def create(self, body: NewReader) -> Reader:
        return Reader(id=8, name=body.name, joined=datetime.date(2026, 10, 12))

    @put("/{reader_id}")
    def rename(self, reader_id: int, body: NewReader, request: Request) -> Response:
        return Response.json(
            {"id": reader_id, "name": body.name, "agent": request.headers["user-agent"]},
            headers={"X-Renamed": "yes"},
        )

    @delete("/{reader_id}")
    async def remove(self, reader_id: int) -> None:
        self.readers.get(reader_id)

    @get("/new")
    async def blank(self) -> dict[str, str]:
        return {"name": ""}


class MiscApi(Router, prefix="/misc"):
    @get("/text")
    async def text(self) -> Response:
        return Response("pong")

    @post("/echo")
    async def echo(self, body: bytes = b"none") -> Response:
        return Response(body)

    @get("/stream")
    async def stream(self) -> Response:
        async def chunks() -> AsyncIterator[bytes | str]:
            yield "a"
            yield b"b"

        return Response(chunks(), media_type="text/event-stream")

    @get("/teapot")
    async def teapot(self) -> None:
        raise HTTPError(418, {"why": "short and stout"}, headers={"x-kind": "tea"})

    @get("/bug")
    async def bug(self) -> None:
        raise ZeroDivisionError("真 bug")

    @post("/accepted", status=202)
    async def accepted(self) -> None:
        return None

    @get("/untyped")
    async def untyped(self) -> Canary | dict[str, int]:
        return {"n": 1}

    @get("/blocking")
    def blocking(self, seconds: float = 0) -> dict[str, int]:
        time.sleep(seconds)
        return {"thread": threading.get_ident()}

    @get("/thread")
    async def thread(self) -> dict[str, int]:
        return {"thread": threading.get_ident()}

    @post("/optional")
    async def optional(self, body: NewReader | None = None) -> dict[str, bool]:
        return {"given": body is not None}


class Api(Router, prefix="/api"):
    readers = dep(ReaderApi)
    misc = dep(MiscApi)


class Library(App):
    api = dep(Api)

    @get
    async def root(self) -> dict[str, str]:
        return {"name": "library"}

    @error(ReaderNotFoundError)
    async def missing(self, request: Request, exc: ReaderNotFoundError) -> Response:
        return Response.json({"msg": f"no reader {exc.reader_id}", "at": request.path}, status=404)


def _client(app: Application) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with running(Library) as library, _client(library) as client:
        yield client


# --- 路由 -------------------------------------------------------------------


async def test_prefixes_add_up_along_the_dependency_edges(http: httpx.AsyncClient) -> None:
    assert (await http.get("/")).json() == {"name": "library"}
    assert (await http.get("/api/readers/7")).json() == {"id": 7, "name": "七", "joined": None}


async def test_a_static_path_wins_over_a_parameter(http: httpx.AsyncClient) -> None:
    assert (await http.get("/api/readers/new")).json() == {"name": ""}


async def test_a_path_nobody_answers_is_404(http: httpx.AsyncClient) -> None:
    for path in ("/nowhere", "/api/readers/7/extra", "/api/readers/"):
        response = await http.get(path)
        assert (response.status_code, response.json()) == (404, {"detail": "Not Found"}), path


async def test_a_method_nobody_answers_is_405_and_says_which_are(http: httpx.AsyncClient) -> None:
    response = await http.patch("/api/readers/7")
    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, GET, PUT"


async def test_head_is_answered_by_get(http: httpx.AsyncClient) -> None:
    assert (await http.head("/api/readers/7")).status_code == 200


# --- 形参绑定 ---------------------------------------------------------------


async def test_query_parameters_are_validated_and_defaulted(http: httpx.AsyncClient) -> None:
    assert (await http.get("/api/readers")).json() == {"keyword": None, "tag": [], "limit": 20}
    response = await http.get("/api/readers?keyword=k&tag=1&tag=2&limit=5")
    assert response.json() == {"keyword": "k", "tag": [1, 2], "limit": 5}


async def test_a_body_is_validated_and_the_status_comes_from_the_mark(
    http: httpx.AsyncClient,
) -> None:
    response = await http.post("/api/readers", json={"name": "八"})
    assert response.status_code == 201
    assert response.json() == {"id": 8, "name": "八", "joined": "2026-10-12"}


async def test_every_failed_parameter_is_reported_at_once_as_422(http: httpx.AsyncClient) -> None:
    response = await http.get("/api/readers?limit=many&tag=x")
    assert response.status_code == 422
    assert [(e["loc"], e["type"]) for e in response.json()["detail"]] == [
        (["query", "tag", 0], "int_parsing"),
        (["query", "limit"], "int_parsing"),
    ]


async def test_a_bad_path_parameter_or_body_is_422(http: httpx.AsyncClient) -> None:
    assert (await http.get("/api/readers/seven")).json()["detail"][0]["loc"] == [
        "path",
        "reader_id",
    ]
    missing = await http.post("/api/readers", json={})
    assert missing.json()["detail"] == [
        {"loc": ["body", "name"], "msg": "Field required", "type": "missing"}
    ]
    broken = await http.post("/api/readers", content=b"{nope")
    assert broken.json()["detail"][0]["type"] == "json_invalid"
    absent = await http.post("/api/readers")
    assert absent.json()["detail"] == [
        {"loc": ["body"], "msg": "Field required", "type": "missing"}
    ]


async def test_a_body_with_a_default_may_be_left_out(http: httpx.AsyncClient) -> None:
    assert (await http.post("/api/misc/optional")).json() == {"given": False}
    assert (await http.post("/api/misc/optional", json={"name": "x"})).json() == {"given": True}
    assert (await http.post("/api/misc/echo")).content == b"none"
    assert (await http.post("/api/misc/echo", content=b"\x00raw")).content == b"\x00raw"


async def test_a_sync_method_and_the_request_object_work(http: httpx.AsyncClient) -> None:
    response = await http.put("/api/readers/7", json={"name": "新"}, headers={"user-agent": "t"})
    assert response.json() == {"id": 7, "name": "新", "agent": "t"}
    assert response.headers["x-renamed"] == "yes"


async def test_a_sync_method_runs_in_a_thread_and_does_not_hold_other_requests(
    http: httpx.AsyncClient,
) -> None:
    """普通 ``def`` 的接口放进线程池：四个各阻塞 0.2 秒的请求并行完成，事件循环照常应答。"""
    loop = (await http.get("/api/misc/thread")).json()["thread"]
    assert loop == threading.get_ident()
    assert (await http.get("/api/misc/blocking")).json()["thread"] != loop

    started = time.perf_counter()
    slow = [asyncio.create_task(http.get("/api/misc/blocking?seconds=0.2")) for _ in range(4)]
    await asyncio.sleep(0.05)
    quick = await http.get("/api/misc/thread")
    answered_after = time.perf_counter() - started
    await asyncio.gather(*slow)
    assert quick.status_code == 200
    assert answered_after < 0.15, "阻塞的同步接口没有卡住事件循环"
    assert time.perf_counter() - started < 0.6, "四个请求是并行的，而不是排队的 0.8 秒"


# --- 响应 -------------------------------------------------------------------


async def test_none_is_an_empty_answer(http: httpx.AsyncClient) -> None:
    removed = await http.delete("/api/readers/7")
    assert (removed.status_code, removed.content) == (204, b"")
    assert (await http.post("/api/misc/accepted")).status_code == 202


async def test_a_response_is_sent_as_it_is(http: httpx.AsyncClient) -> None:
    text = await http.get("/api/misc/text")
    assert (text.text, text.headers["content-type"]) == ("pong", "text/plain; charset=utf-8")
    stream = await http.get("/api/misc/stream")
    assert (stream.text, stream.headers["content-type"]) == ("ab", "text/event-stream")
    assert "content-length" not in stream.headers


async def test_a_return_annotation_that_cannot_be_serialised_falls_back(
    http: httpx.AsyncClient,
) -> None:
    assert (await http.get("/api/misc/untyped")).json() == {"n": 1}


async def test_a_body_cut_short_by_a_disconnect_is_what_arrived() -> None:
    messages = iter(
        [{"type": "http.request", "body": b"ab", "more_body": True}, {"type": "http.disconnect"}]
    )

    async def receive() -> Any:
        return next(messages)

    request = Request({"type": "http"}, receive)
    assert await request.body() == b"ab"
    assert await request.body() == b"ab", "读过一次之后是缓存"


# --- 异常 -------------------------------------------------------------------


async def test_an_http_error_is_answered_with_its_status(http: httpx.AsyncClient) -> None:
    response = await http.get("/api/misc/teapot")
    assert response.status_code == 418
    assert response.json() == {"detail": {"why": "short and stout"}}
    assert response.headers["x-kind"] == "tea"


async def test_a_marked_method_answers_its_exception_type(http: httpx.AsyncClient) -> None:
    response = await http.get("/api/readers/99")
    assert response.status_code == 404
    assert response.json() == {"msg": "no reader 99", "at": "/api/readers/99"}


async def test_an_unhandled_exception_is_500_and_logged_without_leaking(
    http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="canary_framework.web.asgi.app"):
        response = await http.get("/api/misc/bug")
    assert (response.status_code, response.json()) == (500, {"detail": "Internal Server Error"})
    assert "GET /api/misc/bug failed" in caplog.text
    assert "真 bug" in caplog.text


async def test_the_closest_handler_wins_and_http_errors_can_be_restyled() -> None:
    class Styled(Library):
        @error(HTTPError)
        def envelope(self, request: Request, exc: HTTPError) -> Response:
            assert threading.get_ident() != loop, "普通 def 的处理器也在线程池里"
            return Response.json({"code": exc.status, "msg": exc.detail}, status=exc.status)

        @error(Exception)
        async def anything(self, request: Request, exc: Exception) -> dict[str, str]:
            return {"caught": type(exc).__name__}

    loop = threading.get_ident()
    async with running(Styled) as app, _client(app) as http:
        assert (await http.get("/nowhere")).json() == {"code": 404, "msg": "Not Found"}
        assert (await http.get("/api/readers/x")).json()["code"] == 422
        assert (await http.get("/api/readers/99")).json()["msg"] == "no reader 99"
        caught = await http.get("/api/misc/bug")
        assert (caught.status_code, caught.json()) == (200, {"caught": "ZeroDivisionError"})


async def test_a_handler_that_fails_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    class Failing(Library):
        @error(ReaderNotFoundError)
        async def missing(self, request: Request, exc: Exception) -> Response:
            raise HTTPError(410)

        @error(ZeroDivisionError)
        async def worse(self, request: Request, exc: Exception) -> Response:
            raise RuntimeError("处理器自己坏了")

    async with running(Failing) as app, _client(app) as http:
        assert (await http.get("/api/readers/99")).status_code == 410
        with caplog.at_level(logging.ERROR, logger="canary_framework.web.asgi.app"):
            assert (await http.get("/api/misc/bug")).status_code == 500
        assert "处理器自己坏了" in caplog.text


# --- 单元仍是单元 -----------------------------------------------------------


async def test_an_endpoint_is_an_ordinary_method() -> None:
    async with running(Library) as library:
        api = unit(library, ReaderApi)
        assert (await api.show(7)).name == "七"
        with pytest.raises(ReaderNotFoundError):
            await api.show(99)


async def test_it_is_served_by_a_server_over_a_real_socket() -> None:
    class Gateway(Server):
        library = dep(Library)
        port = 0

    async with running(Gateway) as gateway, httpx.AsyncClient() as client:
        response = await client.get(f"http://127.0.0.1:{gateway.port}/api/readers/7")
        assert response.json()["name"] == "七"


async def test_a_subclass_init_can_wrap_the_app_in_middleware() -> None:
    class Wrapped(Library):
        @init
        def wrap(self) -> None:
            inner = self.app

            async def stamped(scope: Any, receive: Any, send: Any) -> None:
                async def stamp(message: Any) -> None:
                    if message["type"] == "http.response.start":
                        message["headers"].append((b"x-stamp", b"1"))
                    await send(message)

                await inner(scope, receive, stamp)

            self.app = stamped

    async with running(Wrapped) as app, _client(app) as http:
        assert (await http.get("/")).headers["x-stamp"] == "1"


async def test_other_scope_types_are_refused_or_ignored() -> None:
    sent: list[Any] = []

    async def send(message: Any) -> None:
        sent.append(message)

    async def receive() -> Any:
        raise AssertionError("not read")

    async with running(Library) as library:
        await library({"type": "websocket", "path": "/"}, receive, send)
        await library({"type": "something-else"}, receive, send)
    assert sent == [{"type": "websocket.close", "code": 1008}]


# --- 它自己就是一个 ASGI 应用 -------------------------------------------------


class Pool(Canary):
    log: ClassVar[list[str]] = []

    @start
    def open(self) -> None:
        self.log.append("pool open")

    @stop
    def close(self) -> None:
        self.log.append("pool close")


class Pooled(App):
    pool = dep(Pool)

    @get("/")
    async def root(self) -> dict[str, list[str]]:
        return {"log": self.pool.log}


@pytest.fixture
def pool_log() -> list[str]:
    Pool.log = []
    return Pool.log


async def _lifespan(app: Application, *incoming: str) -> list[dict[str, Any]]:
    messages = iter({"type": f"lifespan.{name}"} for name in incoming)
    sent: list[dict[str, Any]] = []

    async def receive() -> Any:
        return next(messages)

    async def send(message: Any) -> None:
        sent.append(dict(message))

    await app({"type": "lifespan"}, receive, send)
    return sent


async def test_lifespan_messages_drive_the_graph_when_nothing_else_has(
    pool_log: list[str],
) -> None:
    """交给别的 ASGI 服务器时，图由它的 lifespan 消息驱动：启动时按序就位，停止时逆序回收。"""
    app = Pooled()
    inbox: asyncio.Queue[dict[str, str]] = asyncio.Queue()
    sent: list[str] = []
    started = asyncio.Event()

    async def send(message: Any) -> None:
        sent.append(message["type"])
        started.set()

    serving = asyncio.create_task(app({"type": "lifespan"}, inbox.get, send))
    inbox.put_nowait({"type": "lifespan.startup"})
    await started.wait()
    async with _client(app) as http:
        assert (await http.get("/")).json() == {"log": ["pool open"]}
    inbox.put_nowait({"type": "lifespan.shutdown"})
    await serving
    assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]
    assert pool_log == ["pool open", "pool close"]


async def test_a_graph_canary_started_is_only_acknowledged(pool_log: list[str]) -> None:
    """已经由 Canary 启动的单元收到 lifespan 消息时只应答：不重复启动，也不替别人回收。"""
    async with running(Pooled) as app:
        assert await _lifespan(app, "startup", "shutdown") == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]
        assert pool_log == ["pool open"]
        async with _client(app) as http:
            assert (await http.get("/")).status_code == 200
    assert pool_log == ["pool open", "pool close"]


async def test_a_startup_or_shutdown_failure_is_reported_to_the_server(
    pool_log: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    class WontStart(Pooled):
        @start
        def refuse(self) -> None:
            raise RuntimeError("连不上数据库")

    class WontStop(Pooled):
        @stop
        def refuse(self) -> None:
            raise RuntimeError("关不掉")

    with caplog.at_level(logging.ERROR, logger="canary_framework.web.asgi.app"):
        assert await _lifespan(WontStart(), "startup") == [
            {"type": "lifespan.startup.failed", "message": "RuntimeError: 连不上数据库"}
        ]
        assert pool_log == ["pool open", "pool close"], "已经启动的依赖照常回收"
        sent = await _lifespan(WontStop(), "startup", "shutdown")
    assert [m["type"] for m in sent] == ["lifespan.startup.complete", "lifespan.shutdown.failed"]
    assert "ExceptionGroup" in sent[1]["message"]
    assert "关不掉" in caplog.text, "完整的异常在日志里"
    assert "WontStart failed to start" in caplog.text
    assert "WontStop failed to stop" in caplog.text


async def test_a_request_before_the_lifecycle_says_what_is_missing() -> None:
    with pytest.raises(LifecycleError, match="was asked to serve before its lifecycle began"):
        async with _client(Pooled()) as http:
            await http.get("/")


async def test_any_asgi_server_can_serve_it(pool_log: list[str]) -> None:
    """``uvicorn main:app`` 的那条路：一个没有启动过的单元实例，交给原生的 uvicorn。"""
    import socket

    import uvicorn

    app = Pooled()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, lifespan="on", log_config=None))
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(0.01)
    async with httpx.AsyncClient() as http:
        answer = await http.get(f"http://127.0.0.1:{sock.getsockname()[1]}/")
    server.should_exit = True
    await serving
    sock.close()
    assert answer.json() == {"log": ["pool open"]}
    assert pool_log == ["pool open", "pool close"]


# --- 声明错误在启动时抛出 ----------------------------------------------------


@dataclasses.dataclass
class Point:
    x: int


def _app(**namespace: Any) -> type[App]:
    return type("Broken", (App,), namespace)


class _Twice(App):
    @get("/same")
    async def one(self) -> None: ...

    @get("/same")
    async def two(self) -> None: ...


class _SameShape(App):
    @get("/x/{a}")
    async def one(self, a: int) -> None: ...

    @get("/x/{b}")
    async def two(self, b: int) -> None: ...


class _Unbound(App):
    @get("/x/{a}")
    async def one(self) -> None: ...


class _Variadic(App):
    @get
    async def one(self, *parts: str) -> None: ...


class _BodyByAnotherName(App):
    @post
    async def one(self, point: Point) -> None: ...


class _Unresolvable(App):
    @get
    async def one(self, x: Nowhere) -> None: ...  # type: ignore[name-defined]  # noqa: F821


class _Unvalidatable(App):
    @get
    async def one(self, x: Canary) -> None: ...


@pytest.mark.parametrize(
    ("app", "message"),
    [
        (_Twice, "GET /same is answered twice: by _Twice.one and by _Twice.two"),
        (_SameShape, "is answered twice"),
        (_Unbound, "no parameter for the path parameter 'a'"),
        (_Variadic, "cannot be bound from a request"),
        (_BodyByAnotherName, "point looks like a request body"),
        (_Unresolvable, "cannot resolve its annotations"),
        (_Unvalidatable, "cannot validate x"),
    ],
)
async def test_what_cannot_be_served_fails_the_init(app: type[App], message: str) -> None:
    with pytest.raises(DeclarationError, match=message):
        await app().init()


def test_a_malformed_declaration_fails_where_it_is_written() -> None:
    with pytest.raises(DeclarationError, match="must start with '/' and not end with one"):
        type("Bad", (Router,), {}, prefix="readers")
    with pytest.raises(DeclarationError, match="must start with '/' and not end with one"):
        type("Bad", (Router,), {}, prefix="/readers/")
    with pytest.raises(DeclarationError, match="a path is empty or starts with '/'"):
        get("readers")
    with pytest.raises(DeclarationError, match="name at least one exception type"):
        error()
