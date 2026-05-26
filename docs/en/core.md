# Core Package

The `canary_framework.core` package provides the foundation of the framework: services, modules, configuration, lifecycle, and dependency injection. Everything in Core is framework-agnostic — no web server, no network, just pure business logic wiring.

## Decorator Summary

| Decorator | Purpose | Declares |
|-----------|---------|----------|
| `@service` | Base unit of business logic | `name`, `deps` |
| `@module` | Groups services into a tree | `name`, `services`, `deps` — inherits from `@service` |
| `@on_config` | Runs after wiring, before on_init. Config attributes are instance attributes. | (no arguments — config fields injected by wiring) |
| `@on_init` | Runs after on_config, before on_start | (no arguments — deps and config are instance attributes) |
| `@on_start` | Runs in topological order on `app.start()` | (no arguments) |
| `@on_end` | Runs in reverse order on `app.stop()` | (no arguments) |


## Metadata Types (Internal)

The framework stores metadata on decorated classes as dataclass instances on `__cf_service_meta__`:

```
ServiceMeta              ModuleMeta (extends ServiceMeta)    RouterMeta (extends ServiceMeta)
├── name: str            ├── (inherits all fields)           ├── (inherits all fields)
└── deps: list[type]     └── services: list[type]            ├── prefix: str
                                                            └── tags: list[str]
```

`@module` and `@router` call `@service` internally, then overlay their own richer metadata type.

## Quick Example

```python
from pydantic import BaseModel
from canary_framework import (
    Canary, service, module, on_config, on_init, on_start
)

class DBConfig(BaseModel):
    database_url: str = "sqlite://"
    pool_size: int = 10

class AppConfig(BaseModel):
    db: DBConfig = DBConfig()  # field name matches service name "db"

@service(name="db", deps=[])
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = connect(self.database_url)

    @on_start
    def start(self) -> None:
        self.pool.ping()

@module(name="app", services=[DBService])
class AppModule:
    pass

app = Canary(AppModule)
await app.config(config=AppConfig())
await app.init()
await app.start()
# ...
await app.stop()
```

## Further Reading

- [Services](./services.md) — declaring and using services
- [Modules](./modules.md) — composing services into modules
- [Configuration](./configuration.md) — pydantic BaseModel config, field-name matching
- [Lifecycle](./lifecycle.md) — init / start / end hooks
- [Dependency Injection](./dependency-injection.md) — deps, naming, and resolution

