# Modules

A **module** is a composable group of services, routers, and sub-modules. Under the hood `@module` calls `@service`, so every module is also a valid framework service — it supports dependency injection, lifecycle hooks, and configuration.

`isinstance(meta, ModuleMeta)` distinguishes module metadata from plain service metadata at runtime.

## Minimal

```python
from canary_framework import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

## Full

```python
from canary_framework import module, on_init, on_end

@module(
    name="AppModule",
    config=AppConfig,              # inherited by child services without their own config
    deps=[MonitorService],         # modules can declare their own dependencies too
    services=[DBService, UserService],
)
class AppModule:
    monitor_service: MonitorService
    app_config: AppConfig

    @on_init
    def init(self) -> None:
        self.monitor_service.register(self)

    @on_end
    async def shutdown(self) -> None:
        await self.monitor_service.deregister(self)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Globally unique module name |
| `config` | `type \| None` | `None` | Config class inherited by child services when not declared |
| `deps` | `list[type] \| None` | `None` | Dependencies for the module itself |
| `services` | `list[type] \| None` | `None` | Direct children — `@service`, `@module`, or `@router` classes |

## Config Inheritance

Child services without a declared `config` automatically inherit the parent module's config class:

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule:
    pass

@service(name="DBService")         # no config declared — inherits parent's DBConfig
class DBService:
    db_config: DBConfig

    @on_init
    def init(self) -> None:
        print(self.db_config.url)   # available via inherited config
```

## Module Nesting

Modules support arbitrary nesting depth:

```python
@module(name="Root", services=[SubModuleA, SubModuleB])
class Root:
    pass

@module(name="SubModuleA", services=[ServiceX, ServiceY])
class SubModuleA:
    pass
```

## Routers in Modules

Since `@router` also calls `@service` internally, routers can be placed directly in a module's `services` list:

```python
@router(prefix="/api", deps=[UserService])
class APIRouter:
    user_service: UserService

    @get("/users")
    async def list_users(self) -> list[dict]:
        return await self.user_service.all()

@module(name="App", services=[APIRouter, UserService])
class App:
    pass
```

Routers in the services list are collected, dependency-injected, and lifecycled exactly like regular services. Use `isinstance(meta, RouterMeta)` to distinguish them from plain services at the type level.
