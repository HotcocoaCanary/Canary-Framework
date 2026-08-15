# Dependency Injection

Cocoas declare dependencies with `@cocoa(deps=[...])`. There is no separate DSL and no
`__init__` plumbing — the dependency graph lives in the decorators.

## The contract

```python
@cocoa(deps=[Database, Cache])
class UserService: ...
```

`deps=[...]` is an ordered list of cocoa types. At `start()`, the runtime injects each
dependency onto the instance as an attribute named after the class, in snake_case:

| Dependency type | Injected attribute |
|---|---|
| `Config` | `self.config` |
| `Database` | `self.database` |
| `UserService` | `self.user_service` |

```python
@cocoa(deps=[Database])
class UserService:
    @on_start
    def warm_up(self) -> None:
        self.database.ping()  # injected before @on_start runs
```

Because injection happens at `start()` — not in `__init__` — constructors stay empty and units
are cheap to build. Do not read injected attributes in `__init__`; use `@on_init` or
`@on_start`.

## Resolution

`init()` builds the graph by walking each root's `deps=[...]` transitively and instantiating
every type once. A type that is not decorated with `@cocoa` raises `TypeError`.

Dependencies are resolved by concrete class object — no strings, no forward references:

```python
@cocoa(deps=[Database])
class UserService: ...
```

## Sharing

Each type is instantiated **once per graph**. When several units depend on the same type, they
share the same instance:

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...


@cocoa(deps=[Config])
class Cache: ...


@cocoa(deps=[Database, Cache])
class Root: ...


app = Canary(Root)
await app.start()
assert app[Database].config is app[Cache].config  # same Config
```

Sharing is scoped to a single `Canary`. Two separate `Canary` instances build two independent
graphs.

## Cycles

Cycles are rejected during `init()`. The topological sort detects them and raises
`CircularDependencyError`, which exposes the offending types on `.cycle`:

```python
@cocoa(deps=[B])
class A: ...


@cocoa(deps=[A])
class B: ...


app = Canary(A)
await app.init()  # CircularDependencyError: circular dependency detected: A -> B -> A
```

## Multi-root graphs

Passing several roots to `Canary` unions their graphs. Dependencies shared between the roots
are still instantiated once:

```python
app = Canary(UserService, ReportService)
await app.start()
assert app[UserService].database is app[ReportService].database
```

## Naming edge cases

The injected attribute name comes from the dependency's class name, converted to snake_case.
Acronyms are handled (`APIService` → `api_service`, `HTTPServer` → `http_server`). If two
dependencies would collide on a name, rename one of the classes — the injected attribute is
derived from the type, not from the list order.
