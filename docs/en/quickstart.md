# Quick Start

## Installation

```bash
pip install canary-framework          # core library
pip install canary-framework[web]     # full install with FastAPI support
```

## Minimal Example

```python
import asyncio
from canary_framework import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self) -> None:
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main() -> None:
    app = Canary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

No `@config`, `@on_init`, or `deps` needed — it works out of the box.

## Full Example

With config, dependency injection, and web routing:

```python
import asyncio
from canary_framework import service, module, on_init, Context, config
from canary_framework.web.fastapi import web, get, router, WebCanary

# Config
@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

# Router
@router(prefix="/api")
class APIRouter:
    def __init__(self, ctx: Context) -> None:
        self.svc = ctx.resolve(HelloService)

    @get("/hello")
    async def hello(self) -> dict:
        return await self.svc.greet("world")

# Service
@web(routers=[APIRouter])
@service(name="HelloService", config=AppConfig)
class HelloService:
    @on_init
    async def init(self, ctx: Context) -> None:
        pass

    @on_start
    def start(self) -> None:
        print("start")

    async def greet(self, name: str) -> str:
        return f"Hello, {name}!"

# Module
@web()
@module(name="AppModule", config=AppConfig, services=[HelloService])
class AppModule:
    @get("/health")
    async def health(self) -> dict:
        return {"status": "ok"}


async def main() -> None:
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```
