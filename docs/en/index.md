# Canary Framework 0.6

Canary is a typed async framework built around three explicit layers:

1. **Service** — lifecycle, dependency injection, and domain logic; never ASGI.
2. **Router** — a Service-like dependency consumer plus HTTP routes; the smallest runnable app.
3. **Module** — an explicit child composition and dependency-scope boundary that aggregates Router descendants.

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

## Core guarantees

- Explicit async initialization; lifespan never initializes.
- Annotation-based DI with direction validation and deterministic topological order.
- Scoped parent reuse, sibling isolation, and explicit Service promotion.
- Deterministic prefix, tag, and security propagation.
- One route table and OpenAPI document per runtime root.
- Compile-time checks for route, docs, operation-ID, security, and schema conflicts.

Continue with the [Quick Start](quickstart.md), then read [Services](services.md), [Modules](modules.md), and [Routers](web.md).
