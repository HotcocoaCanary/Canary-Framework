# Modules

## Minimal

```python
from canary_framework import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

## Full

```python
from canary_framework import module, on_init, Context

@module(
    name="AppModule",
    config=AppConfig,           # optional: inherited by child services without their own config
    services=[DBService, UserService],
)
class AppModule:
    @on_init
    def init(self, ctx: Context) -> None:
        pass                    # modules can also have lifecycle hooks

    @on_start
    def start(self) -> None:
        pass
```

## Config Inheritance

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule:
    pass

@service(name="DBService")              # no config declared → inherits parent's DBConfig
class DBService:
    pass
```

## Module Nesting

Modules support arbitrary nesting depth:

```python
@module(name="Root", services=[
    SubModuleA,
    SubModuleB,
])
class Root:
    pass

@module(name="SubModuleA", services=[ServiceX, ServiceY])
class SubModuleA:
    pass
```
