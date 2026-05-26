# Quick Start

## Installation

```bash
pip install canary-framework          # core library
pip install canary-framework[web]     # full install with FastAPI support
```

## Minimal Example

One service, no config, no dependencies — just init and start:

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

## Full Example

Service + router + config + WebCanary:

```python
import asyncio
from canary_framework import service, module, on_init, config
from canary_framework.web.fastapi import get, router, WebCanary

@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

@router(prefix="/api", deps=[], tags=["api"])
class APIRouter:
    @get("/hello")
    async def hello(self) -> dict:
        return {"message": "Hello, world!"}

@service(name="DBService", config=AppConfig)
class DBService:
    app_config: AppConfig

    @on_init
    def init(self) -> None:
        print(f"DB ready at {self.app_config.uvicorn_host}")

@module(name="AppModule", config=AppConfig, services=[APIRouter, DBService])
class AppModule:
    pass

async def main() -> None:
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```
