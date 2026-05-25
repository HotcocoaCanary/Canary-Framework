# Services

## Minimal

```python
from cf import service, on_start

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self):
        print("started")
```

- `name`: globally unique, required
- Everything else is optional

## Full

```python
from cf import service, on_init, Context

@service(
    name="UserService",         # required
    config=UserConfig,          # optional: @config-decorated config class
    deps=[DBService],           # optional: dependency list, auto-injected as self.db_service
)
class UserService:
    @on_init
    def init(self, ctx: Context):
        ctx.config.db_url       # access config
        self.db_service.query() # use injected dependency

    @on_start
    def start(self):
        pass

    @on_end
    def end(self):
        pass
```
