# Quick Start

## Installation

```bash
pip install git+https://github.com/HotcocoaCanary/Canary-Framework.git              # core library
pip install "git+https://github.com/HotcocoaCanary/Canary-Framework.git#egg=cf[web]" # with FastAPI
```

## Minimal Example

```python
import asyncio
from cf import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self):
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main():
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
from cf import service, module, on_init, on_start, Context, config
from cf.web.fastapi import web, get, router, WebCanary

@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

@router(prefix="/api")
class APIRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service

    @get("/hello")
    async def hello(self):
        return await self.svc.greet("world")

@web(routers=[APIRouter])
@service(name="HelloService", config=AppConfig)
class HelloService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        print("start")

    def greet(self, name: str):
        return f"Hello, {name}!"

@web()
@module(name="AppModule", config=AppConfig, services=[HelloService])
class AppModule:
    pass

async def main():
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```
