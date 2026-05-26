# Core Concepts

| Concept | Description | Minimal Declaration | Decorator |
|---------|-------------|---------------------|-----------|
| **Service** | Smallest runtime unit | `@service(name="X")` | `@service` |
| **Module** | Container composing services, itself a service | `@module(name="X", services=[...])` | `@module` |
| **Context** | Unified runtime handle: `get_config` / `get_service` | Auto-injected by framework | — |
| **Config** | pydantic-settings subclass, auto-reads .env | Declared when needed | `@config` |
| **Lifecycle** | `on_init` / `on_start` / `on_end`, managed via `LifecycleHook` enum | Declared when needed | `@on_init` etc. |

## Type-Safe Access

Context provides type-safe access methods:

```python
@on_init
def init(self, ctx: Context) -> None:
    cfg = ctx.get_config(AppConfig)      # type-safe, returns AppConfig
    svc = ctx.get_service(MyService)      # type-safe, returns MyService instance
```



## Context Chain

Each service and module exists in its **own context**, and also within the **parent module's context**. The Context delegates config lookup and dependency resolution upward through the parent chain.

```
AppModule Context (parent=None)
│  config: AppConfig           # auto-loaded from .env by pydantic-settings
│
├── DBService Context (parent → AppModule)
│   config: AppConfig          # no config declared → found via parent module chain
│
├── UserService Context (parent → AppModule)
│   config: UserConfig         # its own
│   get_service(DBService) → ✓     # found in parent module's sub_services chain
│
└── DataSetService Context (parent → AppModule)
    config: DataSetConfig      # its own
    get_service(DBService) → ✓     # same as above
    get_service(UserService) → ✓   # same as above
```
