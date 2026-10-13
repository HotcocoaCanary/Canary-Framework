"""Load-test the application unit against FastAPI, endpoint for endpoint.

同一组接口写两遍，各起一个进程，用同一个压测客户端逐个场景打::

    uv run python benchmarks/web.py
    uv run python benchmarks/web.py --seconds 5 --connections 128 --routes 0

- ``fastapi``：FastAPI 应用，由 ``uvicorn.run`` 服务。
- ``canary``：应用单元（``web.asgi.app``），由服务器单元（``web.asgi.server``）服务。

两边的 HTTP 解析都是 uvicorn，校验与序列化都是 pydantic，所以差别来自二者之间的那一层：
路由查找、形参绑定、依赖解析、响应的组装。服务器单元另外关掉了 Nagle 算法，这对回环上的
短连接复用有影响，也算在 ``canary`` 一侧。

业务接口之后各有 ``--routes`` 条带路径参数的接口，``last`` 场景命中其中最后一条：FastAPI 按
注册顺序逐条匹配，应用单元按段走前缀树。数字只在同一台机器、同一次运行里可比。

压测客户端是本文件里的一个极简 HTTP/1.1 客户端（长连接、不做管线化），自己占若干个进程；
它与服务器抢同一批核，所以绝对数值偏保守。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import signal
import socket
import subprocess
import sys
import time
from typing import Any

from pydantic import BaseModel

HOST = "127.0.0.1"


class Tag(BaseModel):
    name: str
    weight: float = 1.0


class Item(BaseModel):
    id: int
    name: str
    price: float
    tags: list[Tag] = []


class NewItem(BaseModel):
    name: str
    price: float
    tags: list[Tag] = []


ITEMS = [
    Item(id=i, name=f"item-{i}", price=i * 1.5, tags=[Tag(name="a"), Tag(name="b", weight=0.5)])
    for i in range(1000)
]

# ---------------------------------------------------------------- the two servers


def serve_fastapi(port: int, routes: int) -> None:
    import uvicorn
    from fastapi import APIRouter, FastAPI, Query

    api = APIRouter(prefix="/api")

    @api.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    @api.get("/items/{item_id}")
    async def item(item_id: int) -> Item:
        return ITEMS[item_id % 1000]

    @api.get("/search")
    async def search(
        q: str,
        limit: int = 20,
        tag: list[str] = Query(default=[]),  # noqa: B008
    ) -> dict[str, Any]:
        return {"q": q, "limit": limit, "tag": tag}

    @api.post("/items", status_code=201)
    async def create(body: NewItem) -> Item:
        return Item(id=1, name=body.name, price=body.price, tags=body.tags)

    @api.get("/list")
    async def listing(n: int = 100) -> list[Item]:
        return ITEMS[:n]

    @api.get("/sync")
    def sync() -> dict[str, bool]:
        return {"ok": True}

    async def extra(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    for i in range(routes):
        api.add_api_route(f"/r{i}/{{item_id}}", extra, methods=["GET"])

    app = FastAPI()
    app.include_router(api)
    uvicorn.run(app, host=HOST, port=port, log_config=None, access_log=False)


def serve_canary(port: int, routes: int) -> None:
    from canary_framework import dep
    from canary_framework.web.asgi.app import App, Router, get, post
    from canary_framework.web.asgi.server import Server

    # 标记在类体里叫 get，接口方法就不能再叫这个名字。
    class Api(Router, prefix="/api"):
        @get("/ping")
        async def ping(self) -> dict[str, bool]:
            return {"ok": True}

        @get("/items/{item_id}")
        async def item(self, item_id: int) -> Item:
            return ITEMS[item_id % 1000]

        @get("/search")
        async def search(
            self,
            q: str,
            limit: int = 20,
            tag: list[str] = [],  # noqa: B006
        ) -> dict[str, Any]:
            return {"q": q, "limit": limit, "tag": tag}

        @post("/items", status=201)
        async def create(self, body: NewItem) -> Item:
            return Item(id=1, name=body.name, price=body.price, tags=body.tags)

        @get("/list")
        async def listing(self, n: int = 100) -> list[Item]:
            return ITEMS[:n]

        @get("/sync")
        def sync(self) -> dict[str, bool]:
            return {"ok": True}

    for i in range(routes):
        # 标记写在函数对象上，所以每条接口各用一个函数。
        async def extra(self: Any, item_id: int) -> dict[str, int]:
            return {"id": item_id}

        setattr(Api, f"extra{i}", get(f"/r{i}/{{item_id}}")(extra))

    class Web(App):
        api = dep(Api)

    class Gateway(Server, access_log=False):
        web = dep(Web)
        host = HOST

    async def main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        gateway = Gateway()
        gateway.port = port
        async with gateway:
            await stop.wait()

    asyncio.run(main())


SERVERS = {"fastapi": serve_fastapi, "canary": serve_canary}

# ---------------------------------------------------------------- the load


def request(method: str, path: str, body: bytes = b"") -> bytes:
    head = f"{method} {path} HTTP/1.1\r\nHost: bench\r\n"
    if body:
        head += f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
    return head.encode() + b"\r\n" + body


_NEW_ITEM = json.dumps(
    {"name": "widget", "price": 9.9, "tags": [{"name": "a"}, {"name": "b", "weight": 0.5}]}
).encode()


def scenarios(routes: int) -> dict[str, tuple[bytes, bytes]]:
    """场景名 -> （请求，期望的状态码）。"""
    found = {
        "ping": (request("GET", "/api/ping"), b"200"),
        "path": (request("GET", "/api/items/7"), b"200"),
        "query": (request("GET", "/api/search?q=hello&limit=5&tag=a&tag=b"), b"200"),
        "body": (request("POST", "/api/items", _NEW_ITEM), b"201"),
        "list100": (request("GET", "/api/list?n=100"), b"200"),
        "sync": (request("GET", "/api/sync"), b"200"),
        "422": (request("GET", "/api/items/abc"), b"422"),
        "404": (request("GET", "/api/nowhere"), b"404"),
    }
    if routes:
        found["last"] = (request("GET", f"/api/r{routes - 1}/7"), b"200")
    return found


def _worker(
    port: int, data: bytes, seconds: float, connections: int, results: Any
) -> None:  # pragma: no cover - 子进程
    async def one(deadline: float, latencies: list[float], statuses: set[bytes]) -> None:
        reader, writer = await asyncio.open_connection(HOST, port)
        writer.get_extra_info("socket").setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        while time.perf_counter() < deadline:
            began = time.perf_counter()
            writer.write(data)
            head = await reader.readuntil(b"\r\n\r\n")
            at = head.lower().find(b"content-length:")
            if at >= 0:
                await reader.readexactly(int(head[at + 15 : head.index(b"\r\n", at)]))
            latencies.append(time.perf_counter() - began)
            statuses.add(head[9:12])
        writer.close()

    async def main() -> tuple[list[float], set[bytes]]:
        latencies: list[float] = []
        statuses: set[bytes] = set()
        deadline = time.perf_counter() + seconds
        await asyncio.gather(*(one(deadline, latencies, statuses) for _ in range(connections)))
        return latencies, statuses

    results.put(asyncio.run(main()))


def load(
    port: int, data: bytes, expected: bytes, seconds: float, processes: int, connections: int
) -> tuple[float, float, float]:
    """打 *seconds* 秒，返回（每秒请求数，p50 毫秒，p99 毫秒）。"""
    results: Any = multiprocessing.Queue()
    each = max(1, connections // processes)
    workers = [
        multiprocessing.Process(target=_worker, args=(port, data, seconds, each, results))
        for _ in range(processes)
    ]
    for worker in workers:
        worker.start()
    gathered = [results.get() for _ in workers]
    for worker in workers:
        worker.join()
    statuses = set().union(*(statuses for _, statuses in gathered))
    if statuses != {expected}:
        raise SystemExit(f"expected only {expected!r}, got {sorted(statuses)}")
    latencies = sorted(latency for found, _ in gathered for latency in found)
    return (
        len(latencies) / seconds,
        latencies[len(latencies) // 2] * 1000,
        latencies[int(len(latencies) * 0.99)] * 1000,
    )


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def _wait_until_listening(port: int, server: subprocess.Popen[bytes]) -> None:
    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        if server.poll() is not None:
            raise SystemExit(f"the server exited with {server.returncode} before listening")
        with socket.socket() as probe:
            if probe.connect_ex((HOST, port)) == 0:
                return
        time.sleep(0.02)
    raise SystemExit("the server did not start listening within 30 seconds")


def measure(stack: str, args: argparse.Namespace) -> dict[str, tuple[float, float, float]]:
    port = _free_port()
    command = [sys.executable, __file__, "--serve", stack, "--port", str(port)]
    server = subprocess.Popen([*command, "--routes", str(args.routes)])
    try:
        _wait_until_listening(port, server)
        cases = scenarios(args.routes)
        load(port, *cases["ping"], 1.0, args.processes, args.connections)  # 预热
        return {
            name: load(port, data, expected, args.seconds, args.processes, args.connections)
            for name, (data, expected) in cases.items()
        }
    finally:
        server.terminate()
        server.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--seconds", type=float, default=3.0, help="每个场景打多久")
    parser.add_argument("--connections", type=int, default=64, help="并发的长连接数")
    parser.add_argument("--processes", type=int, default=2, help="压测客户端的进程数")
    parser.add_argument("--routes", type=int, default=500, help="额外的带参数接口条数")
    parser.add_argument("--serve", choices=sorted(SERVERS), help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        SERVERS[args.serve](args.port, args.routes)
        return

    measured = {stack: measure(stack, args) for stack in ("fastapi", "canary")}
    print(
        f"{args.connections} connections, {args.seconds:g}s per scenario, "
        f"{args.routes} extra routes\n"
    )
    print(f"{'':9}{'fastapi':>26}{'canary':>26}")
    columns = f"{'req/s':>10}{'p50 ms':>8}{'p99 ms':>8}"
    print(f"{'scenario':9}{columns}{columns}{'ratio':>8}")
    for name in measured["fastapi"]:
        theirs, ours = measured["fastapi"][name], measured["canary"][name]
        cells = "".join(f"{rps:>10.0f}{p50:>8.2f}{p99:>8.2f}" for rps, p50, p99 in (theirs, ours))
        print(f"{name:9}{cells}{ours[0] / theirs[0]:>7.2f}x")


if __name__ == "__main__":
    main()
