# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "canary-framework==1.0.1",
#     "dishka==1.10.1",
#     "dependency-injector==4.49.1",
#     "injector==0.24.0",
#     "fastapi==0.141.1",
#     "httpx",
#     "mypy",
#     "packaging",
# ]
# ///
"""Reproduce the comparison table in docs/*/why-canary.md.

对比页里的每一条都由本脚本实测得出::

    uv run benchmarks/comparison.py

同一个场景在每个库里各写一遍：``Config`` 之上有两个互不依赖的资源 ``Database`` 与
``Cache``（各需 0.1 秒获取），``Service`` 依赖二者。逐项测量：互不依赖的资源是否并发
获取、有依赖的资源是否逆序释放、获取中途失败时已获取的资源何时释放、关闭后能否再次
启动、如何替换依赖，以及 ``mypy --strict`` 推断出的类型。
"""

import asyncio
import contextvars
import importlib.metadata
import os
import threading
import time
import warnings
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from mypy import api as mypy_api
from packaging.requirements import Requirement

warnings.filterwarnings("ignore")

ACQUIRE = 0.1


@dataclass
class Result:
    startup: str = "—"
    reverse_teardown: str = "—"
    failure: str = "—"
    restart: str = "—"
    override: str = "—"
    scoped: str = "—"
    notes: list[str] = field(default_factory=list)


def timed(seconds: float) -> str:
    return f"{seconds:.2f}s"


# --- Canary -------------------------------------------------------------------


async def canary() -> Result:
    from canary_framework import Canary, dep, scope_of, start, stop

    r, log = Result(), []
    fail = False

    class Config(Canary): ...

    class Database(Canary):
        config = dep(Config)

        @start
        async def open(self) -> None:
            await asyncio.sleep(ACQUIRE)
            log.append("db.open")

        @stop
        async def close(self) -> None:
            log.append("db.close")

    class Cache(Canary):
        config = dep(Config)

        @start
        async def open(self) -> None:
            await asyncio.sleep(ACQUIRE)
            if fail:
                raise RuntimeError("cache down")

    class Service(Canary):
        db = dep(Database)
        cache = dep(Cache)

    t = time.perf_counter()
    async with Service():
        r.startup = timed(time.perf_counter() - t)

    log.clear()
    fail = True
    try:
        async with Service():
            pass
    except RuntimeError:
        r.failure = "released automatically" if "db.close" in log else "still held"
    fail = False

    log.clear()
    service = Service()
    async with service:
        pass
    async with service:
        pass
    r.restart = "yes" if log.count("db.open") == 2 else "no"

    class FakeDatabase(Database):
        @start
        async def open(self) -> None: ...

    service = Service()
    scope_of(service).provide(Database, FakeDatabase())
    async with service:
        r.override = "scope_of(root).provide(...)" if isinstance(service.db, FakeDatabase) else "?"

    order: list[str] = []

    class Conn(Canary):
        @stop
        def close(self) -> None:
            order.append("conn")

    class Pool(Canary):
        conn = dep(Conn)

        @stop
        def close(self) -> None:
            order.append("pool")

    async with Pool():
        pass
    r.reverse_teardown = "yes" if order == ["pool", "conn"] else f"no {order}"
    r.scoped = "no (one instance per type per graph)"
    return r


# --- dishka -------------------------------------------------------------------


async def dishka() -> Result:
    from dishka import Provider, Scope, make_async_container, provide

    r, log = Result(), []
    fail = False

    class Config: ...

    class Database: ...

    class Cache: ...

    class Service:
        def __init__(self, db: Database, cache: Cache) -> None:
            self.db = db

    class P(Provider):
        config = provide(Config, scope=Scope.APP)
        service = provide(Service, scope=Scope.APP)

        @provide(scope=Scope.APP)
        async def db(self, config: Config) -> AsyncIterator[Database]:
            await asyncio.sleep(ACQUIRE)
            log.append("db.open")
            yield Database()
            log.append("db.close")

        @provide(scope=Scope.APP)
        async def cache(self, config: Config) -> AsyncIterator[Cache]:
            await asyncio.sleep(ACQUIRE)
            if fail:
                raise RuntimeError("cache down")
            yield Cache()

    container = make_async_container(P())
    t = time.perf_counter()
    await container.get(Service)
    r.startup = timed(time.perf_counter() - t)
    await container.close()

    log.clear()
    fail = True
    container = make_async_container(P())
    try:
        await container.get(Service)
    except RuntimeError:
        r.failure = "released automatically" if "db.close" in log else "held until close()"
    await container.close()
    fail = False

    log.clear()
    container = make_async_container(P())
    for _ in range(2):
        await container.get(Service)
        await container.close()
    r.restart = "yes" if log.count("db.open") == 2 else "no"

    class FakeDatabase(Database): ...

    class Fake(Provider):
        @provide(scope=Scope.APP)
        def db(self) -> Database:
            return FakeDatabase()

    container = make_async_container(P(), Fake())
    service = await container.get(Service)
    r.override = "a later Provider" if isinstance(service.db, FakeDatabase) else "?"
    await container.close()

    order: list[str] = []

    class Conn: ...

    class Pool: ...

    class Q(Provider):
        @provide(scope=Scope.APP)
        async def pool(self, conn: Conn) -> AsyncIterator[Pool]:
            yield Pool()
            order.append("pool")

        @provide(scope=Scope.APP)
        async def conn(self) -> AsyncIterator[Conn]:
            yield Conn()
            order.append("conn")

    container = make_async_container(Q())
    await container.get(Pool)
    await container.close()
    r.reverse_teardown = "yes" if order == ["pool", "conn"] else f"no {order}"

    class Req: ...

    class R(Provider):
        req = provide(Req, scope=Scope.REQUEST)

    container = make_async_container(R())
    async with container() as first:
        a = await first.get(Req)
    async with container() as second:
        b = await second.get(Req)
    await container.close()
    r.scoped = "Scope.REQUEST" if a is not b else "?"
    return r


# --- dependency-injector ------------------------------------------------------


async def dependency_injector() -> Result:
    from dependency_injector import containers, providers

    r, log = Result(), []
    fail = False

    class Config: ...

    class Database: ...

    class Cache: ...

    class Service:
        def __init__(self, db: Database, cache: Cache) -> None:
            self.db = db

    async def open_db(config: Config) -> AsyncIterator[Database]:
        await asyncio.sleep(ACQUIRE)
        log.append("db.open")
        yield Database()
        log.append("db.close")

    async def open_cache(config: Config) -> AsyncIterator[Cache]:
        await asyncio.sleep(ACQUIRE)
        if fail:
            raise RuntimeError("cache down")
        yield Cache()

    class Container(containers.DeclarativeContainer):
        config = providers.Singleton(Config)
        db = providers.Resource(open_db, config=config)
        cache = providers.Resource(open_cache, config=config)
        service = providers.Singleton(Service, db=db, cache=cache)

    c = Container()
    t = time.perf_counter()
    await c.init_resources()  # type: ignore[misc]
    r.startup = timed(time.perf_counter() - t)
    returned = c.service()
    if isinstance(returned, Awaitable):
        r.notes.append("service() returns an awaitable at runtime when resources are async")
        await returned
    await c.shutdown_resources()  # type: ignore[misc]

    log.clear()
    fail = True
    c = Container()
    try:
        await c.init_resources()  # type: ignore[misc]
    except RuntimeError:
        r.failure = (
            "released automatically" if "db.close" in log else "held until shutdown_resources()"
        )
    await c.shutdown_resources()  # type: ignore[misc]
    fail = False

    log.clear()
    c = Container()
    for _ in range(2):
        await c.init_resources()  # type: ignore[misc]
        await c.shutdown_resources()  # type: ignore[misc]
    r.restart = "yes" if log.count("db.open") == 2 else "no"

    fake = Database()
    c = Container()
    with c.db.override(providers.Object(fake)):
        await c.init_resources()  # type: ignore[misc]
        service = await c.service()  # type: ignore[misc]
        r.override = "provider.override(...)" if service.db is fake else "?"
        await c.shutdown_resources()  # type: ignore[misc]

    order: list[str] = []

    async def conn() -> AsyncIterator[str]:
        yield "conn"
        order.append("conn")

    async def pool(conn: str) -> AsyncIterator[str]:
        yield "pool"
        order.append("pool")

    class Ordered(containers.DeclarativeContainer):
        c = providers.Resource(conn)
        p = providers.Resource(pool, conn=c)

    o = Ordered()
    await o.init_resources()  # type: ignore[misc]
    await o.shutdown_resources()  # type: ignore[misc]
    r.reverse_teardown = "yes" if order == ["pool", "conn"] else f"no {order}"

    local = providers.ContextLocalSingleton(object)
    x = contextvars.copy_context().run(local)
    y = contextvars.copy_context().run(local)
    r.scoped = "ContextLocalSingleton" if x is not y else "?"
    return r


# --- injector -----------------------------------------------------------------


async def injector() -> Result:
    from injector import Injector, inject

    r = Result()

    class Database: ...

    class Service:
        @inject
        def __init__(self, db: Database) -> None:
            self.db = db

    lifecycle = [n for n in dir(Injector) if n in {"close", "shutdown", "start", "stop", "aclose"}]
    r.startup = r.reverse_teardown = r.failure = r.restart = (
        "no lifecycle API" if not lifecycle else str(lifecycle)
    )

    class FakeDatabase(Database): ...

    service = Injector([lambda b: b.bind(Database, to=FakeDatabase)]).get(Service)
    r.override = "binder.bind(...)" if isinstance(service.db, FakeDatabase) else "?"

    from injector import threadlocal

    class Local: ...

    per_thread = Injector([lambda b: b.bind(Local, to=Local, scope=threadlocal)])
    got: list[Local] = []
    threads = [threading.Thread(target=lambda: got.append(per_thread.get(Local))) for _ in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    r.scoped = "threadlocal" if got[0] is not got[1] else "?"
    return r


# --- FastAPI Depends ----------------------------------------------------------


async def fastapi_depends() -> Result:
    from typing import Annotated

    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    r, log = Result(), []

    async def get_db() -> AsyncIterator[str]:
        await asyncio.sleep(ACQUIRE)
        log.append("db.open")
        yield "db"
        log.append("db.close")

    async def get_cache() -> AsyncIterator[str]:
        await asyncio.sleep(ACQUIRE)
        yield "cache"

    app = FastAPI()

    @app.get("/")
    async def handler(
        db: Annotated[str, Depends(get_db)], cache: Annotated[str, Depends(get_cache)]
    ) -> str:
        return db

    def run() -> None:
        with TestClient(app) as client:
            t = time.perf_counter()
            client.get("/")
            r.startup = f"{timed(time.perf_counter() - t)} per request"
            client.get("/")
            r.scoped = (
                "per request (default)" if log.count("db.open") == 2 else f"{log.count('db.open')}x"
            )
            app.dependency_overrides[get_db] = lambda: "fake"
            r.override = "app.dependency_overrides" if client.get("/").json() == "fake" else "?"

    await asyncio.to_thread(run)

    order: list[str] = []

    async def conn() -> AsyncIterator[str]:
        yield "conn"
        order.append("conn")

    async def pool(conn: Annotated[str, Depends(conn)]) -> AsyncIterator[str]:
        yield "pool"
        order.append("pool")

    ordered = FastAPI()

    @ordered.get("/")
    async def uses_pool(pool: Annotated[str, Depends(pool)]) -> str:
        return pool

    def run_ordered() -> None:
        with TestClient(ordered) as client:
            client.get("/")

    await asyncio.to_thread(run_ordered)
    r.reverse_teardown = "yes, per request" if order == ["pool", "conn"] else f"no {order}"
    r.failure = r.restart = "per request; app lifetime via lifespan"
    return r


# --- static types -------------------------------------------------------------

TYPE_CHECKS = {
    "canary-framework": """
from canary_framework import Canary, dep
class Database(Canary): ...
class Service(Canary):
    db = dep(Database)
async def f() -> None:
    async with Service() as s:
        reveal_type(s.db)
""",
    "dishka": """
from dishka import Provider, Scope, make_async_container, provide
class Database: ...
class Service:
    def __init__(self, db: Database) -> None:
        self.db = db
class P(Provider):
    db = provide(Database, scope=Scope.APP)
    service = provide(Service, scope=Scope.APP)
async def f() -> None:
    reveal_type(await make_async_container(P()).get(Service))
""",
    "dependency-injector": """
from dependency_injector import containers, providers
class Database: ...
class Service:
    def __init__(self, db: Database) -> None:
        self.db = db
class C(containers.DeclarativeContainer):
    db = providers.Singleton(Database)
    service = providers.Singleton(Service, db=db)
async def f() -> None:
    reveal_type(C().service())
    await C().init_resources()
""",
    "injector": """
from injector import Injector
class Service: ...
reveal_type(Injector().get(Service))
""",
}


def check_types(code: str) -> str:
    # 不读仓库 pyproject.toml 里的 mypy 配置（其中的 files 与 -c 冲突）
    stdout, _, _ = mypy_api.run(
        ["--config-file", os.devnull, "--strict", "--no-incremental", "-c", code]
    )
    notes = [
        line.split("Revealed type is ")[1].strip('"')
        for line in stdout.splitlines()
        if "Revealed type" in line
    ]
    errors = [line.split("error: ")[1] for line in stdout.splitlines() if "error:" in line]
    out = ", ".join(n.removeprefix("__main__.") for n in notes)
    return out + (f"; strict errors: {errors}" if errors else "")


# --- report -------------------------------------------------------------------

LIBRARIES: dict[str, Callable[[], Awaitable[Result]]] = {
    "canary-framework": canary,
    "dishka": dishka,
    "dependency-injector": dependency_injector,
    "injector": injector,
    "fastapi": fastapi_depends,
}


def installs(dist: str) -> list[str]:
    """Third-party distributions pulled in on this interpreter, transitively.

    按当前解释器求值环境标记：只在旧 Python 上才需要的依赖不计入。
    """
    seen: set[str] = set()
    todo = [dist]
    while todo:
        for spec in importlib.metadata.requires(todo.pop()) or []:
            req = Requirement(spec)
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue
            name = req.name.lower().replace("_", "-")
            if name not in seen:
                seen.add(name)
                todo.append(name)
    return sorted(seen)


async def main() -> None:
    rows = [
        ("startup (2 × 0.1s)", "startup"),
        ("reverse teardown", "reverse_teardown"),
        ("failure mid-startup", "failure"),
        ("start again after stop", "restart"),
        ("replace a dependency", "override"),
        ("per-request / context scope", "scoped"),
    ]
    for name, run in LIBRARIES.items():
        result = await run()
        version = importlib.metadata.version(name)
        pulled = installs(name)
        print(
            f"\n## {name} {version} — installs {len(pulled)} third-party: {', '.join(pulled) or '-'}"
        )
        for label, attr in rows:
            print(f"  {label:28} {getattr(result, attr)}")
        if name in TYPE_CHECKS:
            print(f"  {'mypy --strict':28} {check_types(TYPE_CHECKS[name])}")
        for note in result.notes:
            print(f"  note: {note}")


if __name__ == "__main__":
    asyncio.run(main())
