"""Integration — a unit declares what it needs with a class annotation; the runtime fills it.

类级注解即声明：``log: Logger`` / ``config: RepoConfig`` 与 ``deps=[...]`` 是同一件事的
三种写法，运行时在同一个位置填值，抢名字则报错。
"""

from __future__ import annotations

import logging

import pytest
from pydantic_settings import SettingsConfigDict

from canary_framework import Canary, InjectionError, cocoa, on_start
from canary_framework.common.config import Config

pytestmark = pytest.mark.integration


class RepoConfig(Config):
    model_config = SettingsConfigDict(env_prefix="TEST_REPO_", extra="ignore")

    dsn: str = "sqlite://:memory:"
    timeout: float = 5.0


async def test_logger_and_config_are_injected_from_annotations() -> None:
    seen: dict[str, object] = {}

    @cocoa
    class Repository:
        log: logging.Logger
        config: RepoConfig

        @on_start
        async def connect(self) -> None:
            seen["logger"] = self.log.name
            seen["dsn"] = self.config.dsn

    async with Canary(Repository):
        pass

    # logger 名沿用 Python 的惯例（模块 + 类名），因此 dictConfig 里按包配置照常生效。
    assert seen["logger"] == f"{Repository.__module__}.{Repository.__qualname__}"
    assert seen["dsn"] == "sqlite://:memory:"


async def test_environment_variables_feed_the_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_REPO_TIMEOUT", "0.5")

    @cocoa
    class Repository:
        config: RepoConfig

    async with Canary(Repository) as canary:
        assert canary[Repository].config.timeout == 0.5


async def test_one_config_instance_is_shared_by_every_unit_that_declares_it() -> None:
    @cocoa
    class First:
        config: RepoConfig

    @cocoa(deps=[First])
    class Second:
        config: RepoConfig

    async with Canary(Second) as canary:
        assert canary[First].config is canary[Second].config


async def test_config_is_substitutable_through_the_same_overrides_map() -> None:
    @cocoa
    class Repository:
        config: RepoConfig

    substitute = RepoConfig(dsn="postgres://test")
    async with Canary(Repository, overrides={RepoConfig: substitute}) as canary:
        assert canary[Repository].config is substitute


async def test_colliding_attribute_names_are_refused() -> None:
    """``KBFileRepository`` 与 ``KbFileRepository`` 的 snake_case 同名——旧版后写的赢。"""

    @cocoa
    class KBFileRepository:
        pass

    @cocoa
    class KbFileRepository:
        pass

    @cocoa(deps=[KBFileRepository, KbFileRepository])
    class Service:
        pass

    canary = Canary(Service)
    await canary.init()
    with pytest.raises(InjectionError, match="kb_file_repository"):
        await canary.start()


async def test_a_dependency_may_not_squat_on_an_annotated_name() -> None:
    @cocoa
    class Config_:  # noqa: N801 - 故意起一个会撞名的类名
        pass

    Config_.__name__ = "Config"

    @cocoa(deps=[Config_])
    class Service:
        config: RepoConfig

    canary = Canary(Service)
    await canary.init()
    with pytest.raises(InjectionError, match="config"):
        await canary.start()
