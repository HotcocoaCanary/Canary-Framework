# Configuration

Configuration uses `@config` to convert plain Python classes into **pydantic-settings** models with automatic `.env` loading. Config instances are injected as DI attributes (snake_case of the class name) before `on_init`.

## Minimal

```python
from canary_framework import config

@config
class DBConfig:
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
```

**Priority**: environment variable > `.env` file > class default value.

`@config` includes `env_file=".env"` by default — no extra setup needed:

```bash
# .env
DB_URL=postgres://prod:5432/app
DB_POOL_SIZE=20
```

## Accessing Config

Config is injected as an attribute using the snake_case of the config class name:

```python
@service(name="db", config=DBConfig)
class DBService:
    db_config: DBConfig

    @on_init
    def init(self) -> None:
        self.pool = create_pool(self.db_config.url)
```

## Server and FastAPI Parameters via Prefix Routing

The root module's `@config` class uses field-name **prefixes** to route parameters to the correct consumer:

- `uvicorn_*` → `uvicorn.Config`
- `fastapi_*` → `FastAPI()` constructor
- No prefix → business config (untouched by the framework)

```python
@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"    # → uvicorn(host="127.0.0.1")
    uvicorn_port: int = 8000            # → uvicorn(port=8000)
    uvicorn_workers: int = 1            # → uvicorn(workers=1)
    fastapi_title: str = "My API"       # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"     # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None # → disable docs
    db_url: str = "..."                 # business config (no prefix)
```

`WebCanary` automatically splits fields by prefix, strips the prefix, and distributes values to their respective consumers.

## Config Inheritance

Child services without a declared `config` automatically inherit the parent module's config class:

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule:
    pass

@service(name="DBService")         # no config declared → inherits DBConfig
class DBService:
    db_config: DBConfig

    @on_init
    def init(self) -> None:
        print(self.db_config.url)  # available via inherited config
```

## Log Sanitization

Framework logs automatically sanitize sensitive fields. Any field name containing `password`, `secret`, `token`, `key`, `auth`, `credential`, or `private` is replaced with `***` in log output.

```python
@config
class AppConfig:
    db_password: str = "supersecret"    # logged as db_password='***'
    db_url: str = "postgres://..."       # logged normally
```
