# CF (Canary Framework)

Lightweight decorator-driven Python service framework.

**Core philosophy: Services are the minimum unit. Modules compose services. Modules themselves are also services.**

## Packages

| Package | Purpose |
|---------|---------|
| [Core](./core.md) | `@service`, `@module`, `@config`, lifecycle, DI |
| [Web / FastAPI](./fastapi.md) | `@router`, `@get`/`@post`, `WebCanary` — HTTP server |

## Contents

- [Quick Start](./quickstart.md)
- **Core Package**
    - [Overview](./core.md)
    - [Services](./services.md)
    - [Modules](./modules.md)
    - [Configuration](./configuration.md)
    - [Lifecycle](./lifecycle.md)
    - [Dependency Injection](./dependency-injection.md)

- **Web Package**
    - [Overview](./web.md)
    - [FastAPI Integration](./fastapi.md)
- [API Reference](./api-reference.md)
