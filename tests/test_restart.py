"""再次推进：回收之后可以重新启动，失败之后可以重试。"""

from __future__ import annotations

import pytest

from canary_framework import Canary, LifecycleError, Phase, advance, dep, init, start, stop

pytestmark = pytest.mark.functional


async def test_a_stopped_graph_starts_again_without_rerunning_init() -> None:
    seen: list[str] = []

    class Database(Canary):
        @init
        def load(self) -> None:
            seen.append("init")

        @start
        def connect(self) -> None:
            seen.append("start")

        @stop
        def close(self) -> None:
            seen.append("stop")

    class Service(Canary):
        database = dep(Database)

    service = Service()
    async with service:
        pass
    async with service:
        pass

    assert seen == ["init", "start", "stop", "start", "stop"]


async def test_a_failed_start_can_be_retried_after_stop() -> None:
    attempts: list[int] = []

    class Flaky(Canary):
        @start
        def connect(self) -> None:
            attempts.append(len(attempts))
            if len(attempts) == 1:
                raise RuntimeError("boom")

    class Service(Canary):
        flaky = dep(Flaky)

    service = Service()
    with pytest.raises(RuntimeError, match="boom"):
        async with service:
            pass

    async with service:
        pass

    assert attempts == [0, 1]


async def test_a_failed_init_can_be_retried_and_start_waits_for_it() -> None:
    attempts: list[int] = []

    class Flaky(Canary):
        @init
        def load(self) -> None:
            attempts.append(len(attempts))
            if len(attempts) == 1:
                raise RuntimeError("boom")

    class Service(Canary):
        flaky = dep(Flaky)

    service = Service()
    with pytest.raises(RuntimeError, match="boom"):
        await service.init()
    with pytest.raises(LifecycleError, match="@init has not run"):
        await service.start()

    await service.init()
    await service.start()
    await service.stop()

    assert attempts == [0, 1]


async def test_a_failed_start_releases_itself_so_retrying_needs_no_stop() -> None:
    stopped: list[str] = []
    attempts: list[int] = []

    class Flaky(Canary):
        @start
        def connect(self) -> None:
            attempts.append(len(attempts))
            if len(attempts) == 1:
                raise RuntimeError("boom")

        @stop
        def close(self) -> None:
            stopped.append("flaky")

    class Service(Canary):
        flaky = dep(Flaky)

    service = Service()
    await service.init()
    with pytest.raises(RuntimeError):
        await service.start()
    assert stopped == ["flaky"], "the failed start released what it had entered"

    await service.start()
    await service.stop()
    assert stopped == ["flaky", "flaky"], "every entry into @start is paired with one @stop"


async def test_a_phase_that_requires_start_must_run_again_after_a_restart() -> None:
    serve = Phase("serve", after=start)
    seen: list[str] = []

    class Server(Canary):
        @serve
        def listen(self) -> None:
            seen.append("serve")

    server = Server()
    await server.init()
    await server.start()
    await advance(server, serve)
    await server.stop()

    with pytest.raises(LifecycleError, match="@start has not run"):
        await advance(server, serve)

    await server.start()
    await advance(server, serve)
    await server.stop()

    assert seen == ["serve", "serve"]
