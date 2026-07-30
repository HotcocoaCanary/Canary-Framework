# Quick Start

## Standalone Router

A Router is the smallest runnable HTTP application.

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

Initialization is mandatory. Lifespan invokes startup and shutdown only.

## Add domain logic

```python
from canary_framework import get, module, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

@service()
class Counter(ServiceBase):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0

    async def increment(self) -> int:
        self.value += 1
        return self.value

@router(prefix="/counter")
class CounterRouter(RouterBase):
    counter: Counter

    @get("")
    async def increment(self) -> dict[str, int]:
        return {"value": await self.counter.increment()}

@module(children=(CounterRouter,))
class App(ModuleBase):
    pass
```

The Module lists only the Router. `Counter` is discovered transitively from the annotation. Extract endpoint logic into a Service when it needs reuse or non-HTTP testing.

## Lifecycle

Use async `on_init` for structural state, `on_startup` for event-loop-bound resources, and `on_shutdown` for cleanup. Do not override public `init`, `startup`, or `shutdown`.

## Next

Explore the runnable examples and the [API Reference](api-reference.md).
