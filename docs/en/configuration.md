# Configuration

## Minimal: env vars override defaults

```python
from canary_framework import config

@config
class DBConfig:
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
```

pydantic-settings reads with priority: **environment variable > .env file > default value**.

`@config` has built-in `env_file=".env"`:

```bash
# .env file
DB_URL=postgres://prod:5432/app
DB_POOL_SIZE=20
```

```python
@on_init
def init(self, ctx: Context):
    ctx.config.url        # → postgres://prod:5432/app
    ctx.config.pool_size  # → 20
```

## Server & FastAPI params via config

Root module's `@config` class uses **prefixes** to route parameters:

- `uvicorn_*` → uvicorn.Config / uvicorn.Server
- `fastapi_*` → FastAPI() constructor
- No prefix → business config (untouched by framework)

```python
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"      # → uvicorn(host="0.0.0.0")
    uvicorn_port: int = 8000            # → uvicorn(port=8000)
    uvicorn_workers: int = 1            # → uvicorn(workers=1)
    fastapi_title: str = "My API"       # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"     # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None # → disable docs
    db_url: str = "..."                 # business config (no prefix)
```

WebCanary automatically splits by prefix and distributes to respective consumers.
