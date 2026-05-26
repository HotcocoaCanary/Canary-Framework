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
from pydantic import BaseModel
from canary_framework import service, module, on_config
from canary_framework.web.fastapi import get, router, WebCanary

class DBConfig(BaseModel):
    connection_string: str = "postgresql://localhost/mydb"
    pool_size: int = 10

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    dbservice: DBConfig = DBConfig()   # field name matches service name

@router(prefix="/api", deps=[], tags=["api"])
class APIRouter:
    @get("/hello")
    async def hello(self) -> dict:
        return {"message": "Hello, world!"}

@service(name="dbservice")
class DBService:
    @on_config
    def setup(self) -> None:
        print(f"DB ready at {self.connection_string}")

@module(name="AppModule", services=[APIRouter, DBService])
class AppModule:
    pass

async def main() -> None:
    app = WebCanary(AppModule)
    await app.config(config=AppConfig())
    await app.init()
    await app.start()

asyncio.run(main())
```
