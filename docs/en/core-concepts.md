# Core Concepts

| Concept | Description | Minimal Declaration | Decorator |
|---------|-------------|---------------------|-----------|
| **Service** | Smallest runtime unit | `@service(name="X")` | `@service` |
| **Module** | Container composing services, itself a service | `@module(name="X", services=[...])` | `@module` |
| **Context** | Unified runtime handle: config / service / resolve | Auto-injected by framework | `Context` |
| **Config** | pydantic-settings subclass, auto-reads .env | Declared when needed | `@config` |
| **Lifecycle** | on_init / on_start / on_end hooks | Declared when needed | `@on_init` etc. |

## Context Chain

Each service and module exists in its own context, and also within the parent module's context. The Context delegates config and dependency resolution upward through the parent chain.

```
AppModule Context (parent=None)
│  config: AppConfig           # auto-loaded from .env by pydantic-settings
│
├── DBService Context (parent → AppModule)
│   config: AppConfig          # no config declared → inherits from parent module
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
