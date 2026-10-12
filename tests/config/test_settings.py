"""Settings：既是 pydantic 的 BaseSettings，也是图上的单元。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from canary_framework import Canary, dep, init, start
from canary_framework.config import Settings
from canary_framework.test import running

pytestmark = pytest.mark.integration


class AppConfig(Settings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    dsn: str = "sqlite://"
    pool_size: int = 5


class Database(Canary):
    config = dep(AppConfig)

    @start
    def connect(self) -> None:
        self.connected_to = self.config.dsn


class Repository(Canary):
    config = dep(AppConfig)
    database = dep(Database)


def test_it_is_both_a_settings_model_and_a_unit() -> None:
    assert issubclass(Settings, BaseSettings)
    assert issubclass(Settings, Canary)


async def test_the_graph_shares_one_instance_built_from_defaults() -> None:
    async with running(Repository) as repository:
        assert repository.config is repository.database.config
        assert repository.database.connected_to == "sqlite://"


async def test_fields_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DSN", "postgresql://db/prod")
    monkeypatch.setenv("APP_POOL_SIZE", "20")
    async with running(Repository) as repository:
        assert repository.config.dsn == "postgresql://db/prod"
        assert repository.config.pool_size == 20


async def test_a_test_provides_its_own_settings() -> None:
    config = AppConfig(dsn="sqlite://:memory:")
    async with running(Repository, {AppConfig: config}) as repository:
        assert repository.config is config
        assert repository.database.connected_to == "sqlite://:memory:"


async def test_an_invalid_environment_fails_the_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_POOL_SIZE", "many")
    with pytest.raises(ValidationError, match="pool_size"):
        async with running(Repository):
            raise AssertionError("unreachable")


async def test_settings_can_declare_dependencies_and_hooks() -> None:
    class Secrets(Canary):
        token = "s3cret"

    class Derived(Settings):
        secrets = dep(Secrets)
        name: str = "app"
        label: str = ""

        @init
        def derive(self) -> None:
            self.label = f"{self.name}:{self.secrets.token}"

    class Root(Canary):
        config = dep(Derived)

    async with running(Root) as root:
        assert root.config.label == "app:s3cret"


async def test_frozen_settings_still_join_the_graph() -> None:
    class Frozen(Settings):
        model_config = SettingsConfigDict(frozen=True)

        dsn: str = "sqlite://"

    class Root(Canary):
        config = dep(Frozen)

    async with running(Root) as root:
        assert root.config.dsn == "sqlite://"
        with pytest.raises(ValidationError):
            root.config.dsn = "changed"
