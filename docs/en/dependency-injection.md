# Dependency Injection

A cocoa declares its dependencies with `@cocoa(deps=[...])`. No extra DSL, no `__init__` wiring —
the dependency graph lives in the decorator.

## The contract

```python
@cocoa(deps=[Database, Cache])
class UserService: ...
```

`deps=[...]` is an ordered list of cocoa types. At construction the runtime injects each
dependency onto the instance under a name derived from the class name:

| Dependency type | Injected attribute |
|---|---|
| `Config` | `self.config` |
| `Database` | `self.database` |
| `UserService` | `self.user_service` |
| `APIService` | `self.api_service` |
| `HTTPServer` | `self.http_server` |

```python
@cocoa(deps=[Database])
class UserService:
    @on_init
    def check(self) -> None:
        assert self.database is not None  # already injected by @on_init
```

**Injection is assembly, not startup**, which is why it happens in the constructor: when
`Canary(Root)` returns, the wiring is done. `@on_init` can therefore see its collaborators, and
assembly errors — name clashes, "not a cocoa", cycles, units needing constructor arguments — are
raised on the `Canary(Root)` line rather than at some later `await`.

Do not read injected attributes in `__init__`; they do not exist yet. Use `@on_init` or
`@on_start`.

## Where values come from

Units are always constructed with no arguments, so "this unit needs a dsn / an api key / a
timeout" cannot be a constructor parameter. It becomes a dependency:

```python
@cocoa
class Config:
    def __init__(self) -> None:
        self.dsn = os.environ["DATABASE_URL"]
        self.timeout = 5.0


@cocoa(deps=[Config])
class Database:
    @on_init
    def configure(self) -> None:
        self.pool = ConnectionPool(self.config.dsn, timeout=self.config.timeout)
```

This means any unit needing an external value depends on a configuration unit, and that edge
exists only to carry values.

Configuration itself gets no special treatment — it is an ordinary `@cocoa`, and how it reads
environment variables, a `.env` file or a remote config service is up to you (remote reads are
IO, so they belong in `@on_start`).

## Resolution

`Canary(...)` builds the graph by walking `deps=[...]` from every root and instantiating each type
once. A type that is not marked with `@cocoa` raises `TypeError`.

Dependencies are resolved by class object — no strings, no forward references.

## Sharing

Each type is instantiated **once per graph**. Units that depend on the same type share the same
instance:

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
assert app[Database].config is app[Cache].config  # the same Config
```

Sharing is scoped to a single `Canary`; two independent instances build two independent graphs.

**Type is identity.** One type has one instance per graph, so "two `Database` instances pointing
at different servers" cannot be expressed — write two classes if you need two instances.

## Cycles

Cycles are rejected at construction. The topological sort raises `CircularDependencyError` and
exposes the types on the cycle through `.cycle`:

```python
@cocoa(deps=[B])
class A: ...


@cocoa(deps=[A])
class B: ...


Canary(A)  # CircularDependencyError: circular dependency detected: A -> B -> A
```

## Name clashes

The injected attribute name is derived from the dependency's **class name**, independent of the
order in `deps`. When two dependencies produce the same snake_case name, the runtime raises
`InjectionError` instead of letting the last one win:

```python
@cocoa(deps=[KBFileRepository, KbFileRepository])
class Collide: ...

# InjectionError: Collide.kb_file_repository is claimed by more than one source:
#   KBFileRepository, KbFileRepository
```

Rename one of the classes. Acronyms are handled correctly (`APIService` → `api_service`).

## Multi-root graphs

Passing several roots merges their graphs. Dependencies shared between roots are still
instantiated once:

```python
app = Canary(UserService, ReportService)
assert app[UserService].database is app[ReportService].database
```

## Substituting dependencies in tests

The framework provides no substitution entry point. Injection is nothing but attribute
assignment, so a test can do it directly:

```python
service = UserService()
service.database = FakeDatabase()      # exactly what injection does
await service.some_method()
```

When you need the lifecycle too, write the fake as a `@cocoa` unit and compose a test-only graph
with it as a root.
