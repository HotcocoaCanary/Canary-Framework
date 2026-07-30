<h1 align="center">Canary Framework 0.6</h1>

<p align="center">A typed, decorator-driven async framework for Service, Router, and Module applications.</p>

[中文](README_ZH.md) · [Documentation](docs/en/index.md) · [Changelog](CHANGELOG.md)

## Install

```bash
pip install canary-framework
```

Requires Python 3.12+.

## The model

- **Service** owns lifecycle, dependency injection, and domain logic. It is not an ASGI app.
- **Router** is the smallest runnable HTTP application. Keep small endpoint logic inline; extract reusable or non-HTTP-tested logic into Services.
- **Module** explicitly composes `children`, creates dependency scopes, and recursively aggregates descendant Routers.
- A runtime root must be initialized with `await app.init()` before it is served. ASGI lifespan performs startup and shutdown only; it never initializes.
- `on_init` prepares structural state. Event-loop-bound long-lived resources belong in `on_startup`; release them in `on_shutdown`.
- Configuration is root/Module context, not a dependency-injected Service. One root config owns OpenAPI metadata, security schemes, and documentation paths.

## Quick start

```python
import asyncio

import uvicorn

from canary_framework import get, router
from canary_framework.core import RouterBase


@router(prefix="/hello", tags=("Hello",))
class HelloRouter(RouterBase):
    @get("")
    async def hello(self) -> dict[str, str]:
        return {"message": "Hello, Canary!"}


async def setup() -> HelloRouter:
    app = HelloRouter()
    await app.init()
    return app


application = asyncio.run(setup())
uvicorn.run(application, lifespan="on")
```

Open `http://127.0.0.1:8000/hello`, `/docs`, `/redoc`, or `/openapi.json`.

## Composition and transitive DI

```python
from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase


@service()
class Greeting(ServiceBase):
    def message(self, name: str) -> str:
        return f"Hello, {name}!"


@router(prefix="/api")
class ApiRouter(RouterBase):
    greeting: Greeting

    @get("/hello/{name}")
    async def hello(self, name: str) -> dict[str, str]:
        return {"message": self.greeting.message(name)}


@module(children=(ApiRouter,))
class App(ModuleBase):
    pass
```

`Greeting` is discovered transitively through `ApiRouter`; the Module lists only explicit composition nodes. Promote a shared Service to a common parent Module when sibling scopes must reuse one instance.

## HTTP and OpenAPI

Use top-level `@get`, `@post`, `@put`, `@delete`, and `@patch`. Paths may contain path templates (`/{item_id}`) and query templates (`/search?q={query}`). Endpoint metadata supports request/response models, status codes, tags, summaries, descriptions, deprecation, operation IDs, and additional responses.

Nested Module and Router prefixes, tags, and security requirements propagate deterministically. The runtime root compiles one route table and one OpenAPI document. Route, documentation-path, operation-ID, security-scheme, and schema-name conflicts fail during initialization.

## Examples

Ten runnable examples are in [`examples/`](examples), progressing from a standalone Router through nested scopes, validation, OpenAPI, and a layered application. `04_module_aggregation.py` demonstrates recursive route aggregation.

## Breaking release

0.6.0 has no 0.5.x compatibility layer. See [What's New](docs/en/whats-new.md) for the migration table.

## License

Apache-2.0.
