# Core Package

The `canary_framework.core` package provides the foundation of the framework: services, modules, configuration, lifecycle, and dependency injection. Everything in Core is framework-agnostic — no web server, no network, just pure business logic wiring.

## Decorator Summary

| Decorator | Purpose | Declares |
|-----------|---------|----------|
| `@service` | Base unit of business logic | `name`, `deps`, `config` |
| `@module` | Groups services into a tree | `name`, `services`, `deps`, `config` — inherits from `@service` |
| `@config` | Converts a plain class to a pydantic-settings model | type-annotated fields with defaults |
| `@on_init` | Runs after DI + config are ready | (no arguments — deps and config are instance attributes) |
| `@on_start` | Runs in topological order on `app.start()` | (no arguments) |
| `@on_end` | Runs in reverse order on `app.stop()` | (no arguments) |


## Metadata Types (Internal)

The framework stores metadata on decorated classes as dataclass instances on `__cf_service_meta__`:

```
ServiceMeta              ModuleMeta (extends ServiceMeta)    RouterMeta (extends ServiceMeta)
├── name: str            ├── (inherits all fields)           ├── (inherits all fields)
├── deps: list[type]     └── services: list[type]            ├── prefix: str
└── config_cls: type|None                                    └── tags: list[str]
```

`@module` and `@router` call `@service` internally, then overlay their own richer metadata type.

## Quick Example

```python
from canary_framework import (
    Canary, config, service, module, on_init, on_start
)

@config
class AppConfig:
    database_url: str = "sqlite://"

@service(name="db", deps=[], config=AppConfig)
class DBService:
    app_config: AppConfig

    @on_init
    def init(self) -> None:
        self.pool = connect(self.app_config.database_url)

    @on_start
    def start(self) -> None:
        self.pool.ping()

@module(name="app", config=AppConfig, services=[DBService])
class AppModule:
    pass

app = Canary(AppModule)
await app.init()
await app.start()
# ...
await app.stop()
```

## Further Reading

- [Services](./services.md) — declaring and using services
- [Modules](./modules.md) — composing services into modules
- [Configuration](./configuration.md) — @config and config inheritance
- [Lifecycle](./lifecycle.md) — init / start / end hooks
- [Dependency Injection](./dependency-injection.md) — deps, naming, and resolution

