# Configuration

Configuration uses the `@config` decorator and `self.config` access pattern. The config instance passed to `await app.config(config=...)` is propagated to **every** service and module in the tree as `self.config`.

## Defining a Config Class

Use the `@config` decorator to mark any class as a configuration class. It can be a plain Python class or a `pydantic.BaseModel`:

```python
from canary_framework import config

@config
class AppConfig:
    pool_size: int = 10
    timeout: int = 30
    app_name: str = "myapp"
```

You can also use `pydantic.BaseModel` for validation:

```python
from pydantic import BaseModel
from canary_framework import config

@config
class AppConfig(BaseModel):
    pool_size: int = 10
    timeout: int = 30
    app_name: str = "myapp"
```

## Accessing Config in Services

Every service and module in the tree accesses config via `self.config`:

```python
@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.config.pool_size, self.config.timeout)
```

## Passing Config to the App

```python
app = Canary(MyRootModule)
await app.config(config=AppConfig())  # wiring + on_config hooks
await app.init()                       # on_init hooks
await app.start()
await app.stop()
```

`app.config()` performs wiring (dependency injection), propagates the config instance, and then invokes all `@on_config` hooks in topological order. `self.config` is already available when `on_config` runs.

## Server and FastAPI Parameters via Prefix Routing

For `WebCanary`, the root config model's fields with `uvicorn_` or `fastapi_` prefixes are automatically routed:

- `uvicorn_*` → `uvicorn.Config`
- `fastapi_*` → `FastAPI()` constructor
- No prefix → business config (accessible via `self.config`)

```python
@config
class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"     # → uvicorn(host="127.0.0.1")
    uvicorn_port: int = 8000             # → uvicorn(port=8000)
    uvicorn_workers: int = 1             # → uvicorn(workers=1)
    fastapi_title: str = "My API"        # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"       # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None  # → disable docs
    pool_size: int = 10                  # business config field
```

`WebCanary` automatically splits fields by prefix, strips the prefix, and distributes values to their respective consumers.

## Per-Module Config

Modules can declare their own config class via the `config=` parameter. All services in that module (and nested sub-modules without their own config) receive the module's config instance:

```python
@config
class DBModuleConfig:
    dsn: str = "postgres://localhost/test"
    pool_size: int = 5

@module(name="db_module", services=[DBService], config=DBModuleConfig)
class DBModule:
    pass

# DBService.config is DBModuleConfig()
```

If a module does not declare `config=`, it inherits the nearest ancestor's config. The root config is the ultimate fallback.

## Log Sanitization

Framework logs automatically sanitize sensitive fields. Any field name containing `password`, `secret`, `token`, `key`, `auth`, `credential`, or `private` is replaced with `***` in log output.

```python
@config
class AppConfig(BaseModel):
    db_password: str = "supersecret"     # logged as db_password='***'
    db_url: str = "postgres://..."       # logged normally
```
