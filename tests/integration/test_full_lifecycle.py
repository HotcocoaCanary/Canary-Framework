"""Integration — a realistic multi-tier app driven through its full lifecycle."""

import pytest

from canary_framework import (
    Canary,
    LifecycleState,
    cocoa,
    on_init,
    on_start,
    on_stop,
)

pytestmark = pytest.mark.integration


def test_full_lifecycle_order_and_singleton_sharing() -> None:
    # 闭包内的列表由各钩子就地追加，用于断言全局执行顺序。
    events: list[str] = []

    @cocoa
    class Config:
        @on_init
        def load(self) -> None:
            events.append("config.load")

    @cocoa(deps=[Config])
    class Database:
        @on_init
        def migrate(self) -> None:
            events.append("db.migrate")

        @on_start
        def connect(self) -> None:
            events.append("db.connect")

        @on_stop
        def disconnect(self) -> None:
            events.append("db.disconnect")

    @cocoa(deps=[Database])
    class Repository:
        @on_start
        def warm_cache(self) -> None:
            events.append("repo.warm_cache")

        @on_stop
        def flush(self) -> None:
            events.append("repo.flush")

    @cocoa(deps=[Repository])
    class Service:
        @on_start
        def start(self) -> None:
            events.append("service.start")

        @on_stop
        def stop(self) -> None:
            events.append("service.stop")

    @cocoa(deps=[Service])
    class App:
        @on_start
        def banner(self) -> None:
            events.append("app.banner")

    with Canary(App) as canary:
        assert canary.state is LifecycleState.STARTED
        assert canary.order == (Config, Database, Repository, Service, App)

        # 依赖在启动前注入，且全图共享同一单例。
        assert canary[App].service is canary[Service]
        assert canary[Service].repository is canary[Repository]
        assert canary[Repository].database is canary[Database]
        assert canary[Database].config is canary[Config]

    assert canary.state is LifecycleState.STOPPED
    # 启动序按拓扑、停止序按逆拓扑，中间各层的钩子恰好对齐。
    assert events == [
        "config.load",
        "db.migrate",
        "db.connect",
        "repo.warm_cache",
        "service.start",
        "app.banner",
        "service.stop",
        "repo.flush",
        "db.disconnect",
    ]


def test_instances_and_getitem() -> None:
    @cocoa
    class Config:
        pass

    @cocoa(deps=[Config])
    class Database:
        pass

    canary = Canary(Database)
    canary.init()
    canary.start()

    # instances 与 order 同序，__getitem__ 按类型取回对应单例。
    assert canary.instances == (canary[Config], canary[Database])
    assert isinstance(canary[Database], Database)


def test_getitem_raises_key_error_for_unknown_type() -> None:
    @cocoa
    class Known:
        pass

    class Unknown:
        pass

    canary = Canary(Known)
    canary.init()
    canary.start()

    with pytest.raises(KeyError):
        canary[Unknown]
