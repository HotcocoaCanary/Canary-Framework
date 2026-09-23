# Upgrading from 0.9.x

0.10.0 rewrote the core, and 1.0 keeps that core. Coming from 0.9.x, the public API is not
compatible and there is no compatibility layer; this page lists what changed and how to migrate.
Then read [What's New in 1.0](whats-new.md) for the additions since 0.10.

## A unit is a base class

The `@cocoa` decorator and the `Canary` runtime container are both gone. Subclass `Canary` and
the unit runs its own life:

```python
class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None: ...

    @stop
    async def close(self) -> None: ...


async with UserService() as service:      # the whole graph comes up in dependency order
    ...
```

A base class rather than a decorator so that `service.init()`, `async with service` and
`self.config` are all visible to type checkers and IDEs — a decorator cannot widen a class's
static type.

## `dep()` replaces `deps=[...]`

Dependencies are declared with a descriptor instead of listed in a decorator argument:

```python
class AlertDispatcher(Canary):
    sink = dep(LoggingAlertSink)
```

- **You choose the attribute name.** It is no longer the snake_case of the dependency's class
  name, so an implementation can be bound under an abstract name.
- **The type is inferred.** `self.sink` is a `LoggingAlertSink` with no extra annotation.
- **The declaration never needs evaluating**, so it is unaffected by
  `from __future__ import annotations`, `if TYPE_CHECKING` or function-local classes. 0.9.x's
  class-level annotation injection failed silently in all three cases.

## Phases are first-class

`@init` / `@start` / `@stop` are `Phase` instances — both decorators and engine arguments.
Adding a phase requires no registration:

```python
migrate = Phase("migrate", after=init)
```

`after` declares a predecessor, so calling `start()` without `init()` raises `LifecycleError`
instead of silently skipping a phase.

## Overriding means overriding

Hooks resolve by attribute name, matching ordinary method semantics: a subclass overriding a
hook of the same name replaces it, and `super()` composes. 0.9.x deduplicated by function
identity, which turned an override into an addition.

Lifecycle methods can be overridden too:

```python
class Traced(Canary):
    async def start(self) -> None:
        log.info("starting")
        await super().start()
```

## The engine is two functions

Phases of your own are driven by two functions, which `Canary`'s methods wrap:

- `enter(unit, phase)` enters a phase across the dependency graph, dependencies first;
- `leave(unit, phase)` leaves it, the unit first.

The runtime container and its separate lifecycle state machine are gone; each unit keeps its
own state in the scope's dependency graph. Dependency-chain depth is no longer bounded by
Python's recursion limit (previously about 493). See [Architecture](architecture.md).

## Removed

- `@cocoa`, the `Canary(*roots)` runtime container, `canary.order`, `canary.instances`,
  `canary[Type]`, `canary.lifespan`, `start_concurrency=`, the assembly summary and the
  event-loop lag probe.
- `LifecycleState` and its eight-state machine.
- snake_case-by-class-name injection, class-level annotation injection, `Config` and logger
  injection.
- `canary_framework.web` was removed during 0.9.3 development and is not restored here.

## Migration

| 0.9.x | 1.0 |
|---|---|
| `@cocoa(deps=[Database])` + `self.database` | `class X(Canary)` + `database = dep(Database)` |
| `@on_init` / `@on_start` / `@on_stop` | `@init` / `@start` / `@stop` |
| `canary = Canary(Root)` | `root = Root()` |
| `await canary.init()` / `.start()` / `.stop()` | `await root.init()` / `.start()` / `.stop()` |
| `async with Canary(Root) as c` | `async with Root() as root` |
| `canary[Database]` | Read it from a unit that declares it, or `scope_of(root).instances[Database]` |
| `Canary(Root, start_concurrency=8)` | Concurrency is the default; nothing to configure |
| `app = FastAPI(lifespan=canary.lifespan)` | Write the three-line `asynccontextmanager` yourself |
