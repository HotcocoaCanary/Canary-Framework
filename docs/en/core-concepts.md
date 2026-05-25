# Core Concepts

| Concept | Description | Minimal Declaration | Decorator |
|---------|-------------|---------------------|-----------|
| **Service** | Smallest runtime unit | `@service(name="X")` | `@service` |
| **Module** | Container composing services, itself a service | `@module(name="X", services=[...])` | `@module` |
| **Context** | Unified runtime handle: `config_as` / `service_as` / `resolve` | Auto-injected by framework | — |
| **Config** | pydantic-settings subclass, auto-reads .env | Declared when needed | `@config` |
| **Lifecycle** | `on_init` / `on_start` / `on_end`, managed via `LifecycleHook` enum | Declared when needed | `@on_init` etc. |

## Type-Safe Access

Context provides type-safe access methods:

```python
@on_init
def init(self, ctx: Context) -> None:
    cfg = ctx.config_as(AppConfig)      # type-safe, returns AppConfig
    db = ctx.resolve(DBService)          # type-safe, returns DBService instance
    svc = ctx.service_as(MyService)      # type-safe, returns MyService instance
```

The old `ctx.config` and `ctx.service` properties are deprecated, returning `object` type. Use the new type-safe methods instead.

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
│   resolve(DBService) → ✓     # found in parent module's sub_services chain
│
└── DataSetService Context (parent → AppModule)
    config: DataSetConfig      # its own
    resolve(DBService) → ✓     # same as above
    resolve(UserService) → ✓   # same as above
```
