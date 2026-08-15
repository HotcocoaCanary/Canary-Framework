# Dependency Injection

Canaries express dependencies with constructor type annotations. There is no separate DSL — the dependency graph lives in the type definitions themselves.

## The contract

A `__init__` parameter is a dependency when it:

- has a **class annotation** (or a **string forward reference**), and
- has **no default value**.

```python
@canary
class UserService:
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache
```

Rules:

- A parameter with a default value is never injected.
- An unannotated parameter, or one annotated with a non-class type, must have a default — otherwise `RegistrationError` is raised at decoration time.
- `*args` and `**kwargs` are rejected with `RegistrationError`.

## Resolution

The framework reads `inspect.signature` and `typing.get_type_hints` to resolve dependencies. Parameter names are classified at decoration time; concrete types are resolved at graph-build time, so forward references work.

Every resolved dependency must itself be a registered Canary. Depending on a plain class raises `DependencyError`.

## Forward references

Because dependencies are resolved after registration, string forward references work — provided the Canary types are defined at **module level**:

```python
from __future__ import annotations


@canary
class Database:
    def __init__(self, config: "Config") -> None:  # forward reference
        self.config = config


@canary
class Config:
    pass
```

Forward references resolve against module globals. Canaries defined inside a function body cannot resolve forward references reliably — define them at module level instead.

## Cycles

Cycles are rejected. The graph detects them during topological sorting and raises `CircularDependencyError`:

```python
@canary
class A:
    def __init__(self, b: "B") -> None: ...


@canary
class B:
    def __init__(self, a: A) -> None: ...


flock = A.run()
await flock.start()  # CircularDependencyError: Circular dependency detected: A -> B -> A
```

## Scoping

Each Canary type is instantiated **once per `Flock` graph**. When several Canaries depend on the same type, they share the same instance:

```python
@canary
class Database:
    def __init__(self, config: Config) -> None: ...


@canary
class Cache:
    def __init__(self, config: Config) -> None: ...


@canary
class Root:
    def __init__(self, database: Database, cache: Cache) -> None: ...


flock = Root.run()
await flock.start()
assert flock[Database].config is flock[Cache].config
```
