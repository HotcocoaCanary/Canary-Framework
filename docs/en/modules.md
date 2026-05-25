# Modules

## Minimal

```python
from cf import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

## Full

```python
from cf import module, on_init, on_start, Context

@module(
    name="AppModule",
    config=AppConfig,           # optional: inherited by child services without their own config
    services=[DBService, UserService],
)
class AppModule:
    @on_init
    def init(self, ctx: Context):
        pass                    # modules can also have lifecycle hooks

    @on_start
    def start(self):
        pass
```

## Config Inheritance

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule: ...

@service(name="DBService")              # no config declared → inherits parent's DBConfig
class DBService: ...
```
