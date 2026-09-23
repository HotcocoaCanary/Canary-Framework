# Dependencies

## `dep()`

Declare a dependency in the class body:

```python
from canary_framework import Canary, dep


class UserService(Canary):
    database = dep(Database)
    cache = dep(Cache)
```

It is a descriptor that resolves to the shared instance from the owner's scope. Three
properties:

**You choose the attribute name.** The injected name does not come from the dependency's class
name, so an implementation class can be bound under an abstract name:

```python
class AlertDispatcher(Canary):
    sink = dep(LoggingAlertSink)     # self.sink, not self.logging_alert_sink
```

**The type is inferred.** `dep()` is typed to return an instance of what it is given, so
`database` has type `Database` with no extra annotation. Type checkers and IDEs see it.

**The declaration never needs evaluating.** The descriptor holds the class object itself, not
a name, so it is unaffected by `from __future__ import annotations`, `if TYPE_CHECKING`, or
class definitions inside a function.

## Only units may be dependencies

```python
class Plain: ...


class Broken(Canary):
    thing = dep(Plain)
```

```
DeclarationError: dep(<class 'Plain'>): not a Canary subclass
```

The check happens while the class body is evaluated, so the error points at the `dep(...)`
line. Type checkers reject it as well, because `dep()`'s type parameter is bound to `Canary`.

## When dependencies become available

Dependencies exist from `@init` onward, not in `__init__`:

```python
class Broken(Canary):
    config = dep(Config)

    def __init__(self) -> None:
        print(self.config)      # LifecycleError
```

```
LifecycleError: Broken.config is unavailable before the lifecycle begins.
Dependencies exist from @init onward, not in __init__.
```

## Scopes: one scope is one graph

The state one run shares lives in a `Scope`. It is created by the **first unit to be driven**,
which is that graph's root; every other instance is constructed by the framework and registered
into the same scope.

**One instance per type per scope.** A diamond yields one shared instance:

```python
class Left(Canary):
    config = dep(Config)


class Right(Canary):
    config = dep(Config)


class Root(Canary):
    left = dep(Left)
    right = dep(Right)


root = Root()
await root.init()
assert root.left.config is root.right.config      # the same object
```

**Two separately constructed roots are two unrelated graphs.** Even shared dependencies are
distinct:

```python
a, b = Root(), Root()
await a.init()
await b.init()
assert a.left is not b.left
assert a.left.config is not b.left.config
```

Use `scope_of()` to inspect a scope:

```python
from canary_framework import scope_of

scope = scope_of(root)
scope.instances          # type -> instance
scope.entered["start"]   # type -> unit that entered start, in entry order
```

## Cycles

```python
class A(Canary): ...


class B(Canary):
    a = dep(A)


A.b = dep(B)
```

```
CircularDependencyError: circular dependency: A -> B -> A
```

The dependency graph is built before any hook runs, so a cycle is reported before anything
starts — even units on unrelated branches. The exception carries the path that reaches it. Cycles are hard to write in practice: `dep(B)`
is evaluated in the class body, so `B` must already exist and a direct mutual dependency cannot
be expressed.
