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

- **Decorator API** — `@service` / `@module` / `@config`, no base class inheritance needed
- **Topological Startup** — Kahn's algorithm ensures dependencies start first
- **Dependency Injection** — `deps=[DBService]` auto-injected as `self.db_service`
- **Config Management** — `@config` + pydantic-settings, auto-reads `.env` and env vars
- **Lifecycle Hooks** — `@on_init` / `@on_start` / `@on_end`, sync/async adaptive
- **Web Integration** — `WebCanary` for one-click FastAPI + Uvicorn
- **Context System** — parent chain delegates config and dependency resolution upward
- **Type Safety** — `ctx.config_as(Type)` / `ctx.service_as(Type)` with full IDE inference
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

if __name__ == "__main__":
    async def main() -> None:
        app = Canary(App)
        await app.init()
        await app.start()

    asyncio.run(main())
```

## Web Example

```python
import asyncio
from canary_framework import config, module
from canary_framework.web.fastapi import web, get, WebCanary

@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

@web()
@module(name="AppModule", config=AppConfig, services=[])
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

## Documentation

📖 Full documentation: [Canary Framework Docs](https://HotcocoaCanary.github.io/Canary-Framework/)

中文文档: [docs/zh/](./docs/zh/) · English: [docs/en/](./docs/en/)

## Architecture

```
src/canary_framework/
├── core/
│   ├── decorators/          # @config, @service, @module, @on_init/start/end
│   ├── engine/              # Canary, Context, Injector, Sorter
│   ├── registry/            # Registry (dataclass ServiceEntry)
│   └── utils/               # Naming utilities
└── web/
    └── fastapi/             # WebCanary engine, @web, @router, @get/@post/...
```

```
Canary.init()
  ├── _collect()            recursively discover @service/@module
  ├── _validate()           validate dependency integrity
  ├── topological_sort()    Kahn topological sort
  ├── _build_context_tree() build Context parent chain
  └── per topology: DI → config loading → on_init(ctx)
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
