<p align="center">
  <h1 align="center">Canary Framework</h1>
  <p align="center">Lightweight Python Service Framework — Decorator-Driven, Zero Boilerplate</p>
</p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/canary-framework/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python"></a>
</p>

---

Canary Framework is a **decorator-driven** service framework. Core philosophy: **Services are the minimum unit. Modules compose services. Modules themselves are also services.**

## Features

- **Decorator API** — `@service` / `@module`, no base class inheritance needed
- **Topological Startup** — Kahn's algorithm ensures dependencies start first
- **Dependency Injection** — `deps=[DBService]` auto-injected as `self.db_service`
- **Config Management** — pydantic-settings + `app.config(config=...)`, auto-reads `.env` and env vars
- **Lifecycle Hooks** — `@on_config` / `@on_init` / `@on_start` / `@on_end`, sync/async adaptive
- **Web Integration** — `WebCanary` for one-click FastAPI + Uvicorn
- **Log Sanitization** — sensitive config fields (password, secret, token) automatically masked

## Installation

```bash
pip install canary-framework          # core library
pip install canary-framework[web]     # with FastAPI support
```

## Quick Start

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
    await app.config()
    await app.init()
    await app.start()

asyncio.run(main())
```

## Web Example

```python
import asyncio
from pydantic import BaseModel
from canary_framework import service, module, on_config, on_start, Canary
from canary_framework.web.fastapi import router, get, WebCanary

class DBConfig(BaseModel):
    connection_string: str = "postgresql://localhost/mydb"
    pool_size: int = 10

class AppConfig(BaseModel):
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"
    dbservice: DBConfig = DBConfig()

@service(name="dbservice")
class DBService:
    @on_config
    def setup(self) -> None:
        print(f"DB ready at {self.connection_string}")

@router(prefix="/api", tags=["api"])
class APIRouter:
    @get("/hello")
    async def hello(self) -> dict:
        return {"message": "Hello, world!"}

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

## Documentation

📖 Full documentation: [Canary Framework Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

中文文档: [docs/zh/](./docs/zh/) · English: [docs/en/](./docs/en/)

## Architecture

```
src/canary_framework/
├── common/                  # Shared types, enums, exceptions, logging
├── core/
│   ├── decorators/          # @service, @module, lifecycle hooks
│   ├── conductor/           # Canary engine (lifecycle orchestrator)
│   ├── container/           # Registry (service storage/lookup)
│   └── algorithms/          # Topological sort, DI injector, naming
└── web/
    └── fastapi/             # WebCanary engine, @router, @get/@post/...
```

```
Canary.config()
  ├── _collect()            recursively discover @service/@module
  ├── _validate()           validate dependency integrity
  ├── topological_sort()    Kahn topological sort
  ├── instantiate()         create all service instances
  ├── _wire_entry()         DI + config injection + sub-service injection
  └── on_config hooks       (topological order)
Canary.init()
  └── per topology: on_init()
Canary.start()
  └── per topology: on_start()
Canary.stop()
  └── reverse order: on_end()
```

## Community

- 💬 [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions)
- 🐛 [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues)
- 📖 [Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[Apache 2.0](./LICENSE) · Copyright 2026 张文博 (Canary)
