# Configuration

Config uses **pydantic BaseModel** classes passed to `await app.config(config=Model())`. Field names in the model match service/module names — each field's value is injected as attributes on the corresponding service during `app.config()`.

## Defining Config

```python
from pydantic import BaseModel

class DBConfig(BaseModel):
    pool_size: int = 10
    timeout: int = 30

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    db: DBConfig = DBConfig()           # field name matches service name "db"
    user: dict = {"max_items": 100}     # dict works too
```

## Field-Name Matching

The config model's field name must match the `name` of the target service/module. During `app.config()`, each field's value is injected as instance attributes on the matching service.

```python
@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = create_pool(self.pool_size, self.timeout)
        # pool_size and timeout are injected from DBConfig
```

## Passing Config to the App

```python
app = Canary(MyRootModule)
await app.config(config=AppConfig())  # wiring + on_config hooks
await app.init()                       # on_init hooks
await app.start()
await app.stop()
```

`app.config()` performs wiring (dependency injection) and then invokes all `@on_config` hooks in topological order. Config attributes are already available on `self` when `on_config` runs.

## Server and FastAPI Parameters via Prefix Routing

For `WebCanary`, the root config model's fields with `uvicorn_` or `fastapi_` prefixes are automatically routed:

- `uvicorn_*` → `uvicorn.Config`
- `fastapi_*` → `FastAPI()` constructor
- No prefix → business config (untouched by the framework)

```python
class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"     # → uvicorn(host="127.0.0.1")
    uvicorn_port: int = 8000             # → uvicorn(port=8000)
    uvicorn_workers: int = 1             # → uvicorn(workers=1)
    fastapi_title: str = "My API"        # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"       # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None  # → disable docs
    db: DBConfig = DBConfig()            # business config field
```

`WebCanary` automatically splits fields by prefix, strips the prefix, and distributes values to their respective consumers.

## Log Sanitization

Framework logs automatically sanitize sensitive fields. Any field name containing `password`, `secret`, `token`, `key`, `auth`, `credential`, or `private` is replaced with `***` in log output.

```python
class AppConfig(BaseModel):
    db_password: str = "supersecret"     # logged as db_password='***'
    db_url: str = "postgres://..."       # logged normally
```
