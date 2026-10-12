# Configuration

`canary_framework.config` is one class: `Settings`, which is both a
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
`BaseSettings` and a unit.

```bash
pip install "canary-framework[config]"
```

!!! note "Provisional API"
    Extensions may change in a minor release until they are declared stable — see
    [Versioning & Compatibility](../versioning.md#extensions).

## Usage

```python
from canary_framework import Canary, dep, start
from canary_framework.config import Settings
from pydantic_settings import SettingsConfigDict


class AppConfig(Settings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    dsn: str = "sqlite://"
    pool_size: int = 5


class Database(Canary):
    config = dep(AppConfig)

    @start
    async def connect(self) -> None:
        self.pool = await open_pool(self.config.dsn, size=self.config.pool_size)
```

Reading the environment and `.env`, and validating types, is all pydantic-settings — written
exactly as its own docs describe. `Settings` adds one thing: it is a unit, so whoever needs it
writes `dep(AppConfig)` and the whole graph shares one instance.

Invalid configuration raises its validation error while starting, and whatever already started
is reclaimed as usual.

## No-argument construction

The framework constructs every unit with no arguments, settings included: every field must be
obtainable from a default or from the environment.

## Different settings in a test

```python
from canary_framework.test import running

async with running(Service, {AppConfig: AppConfig(dsn="sqlite://:memory:")}) as service:
    ...
```

## Dependencies and hooks of its own

`Settings` is an ordinary unit, so it can declare dependencies and hooks. A `dep()` inside the
model is not taken for a field:

```python
class AppConfig(Settings):
    secrets = dep(SecretStore)

    dsn: str = "sqlite://"
    password: str = ""

    @init
    def load_password(self) -> None:
        self.password = self.secrets.read("db-password")
```

An attribute assigned in a hook must be a declared field — that is pydantic's rule for models.
Fields cannot be named `init` / `start` / `stop`; those are the unit's methods.
