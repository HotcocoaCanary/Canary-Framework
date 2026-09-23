# Canary Framework

**Dependency injection** and **lifecycle** for plain Python classes. Standard library only,
zero third-party dependencies.

Subclass `Canary` and you have a unit: it declares what it depends on, and what it does in
each phase. Start one unit and its dependencies come up in dependency order; leaving reclaims
them in reverse.

```python
import asyncio

from canary_framework import Canary, dep, init, start, stop


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "postgresql://localhost/dev"


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        print(f"connecting to {self.config.dsn}")

    @stop
    async def close(self) -> None:
        print("disconnected")


class UserService(Canary):
    database = dep(Database)


async def main() -> None:
    async with UserService() as service:
        print(service.database.config.dsn)


asyncio.run(main())
```

## Two rules

The whole framework is two rules.

**Advancing** recurses along dependencies: a unit enters a phase only after its dependencies
have completed that phase. One unit runs one phase exactly once no matter how many units
depend on it, and independent dependencies advance concurrently.

**Unwinding** is linear, driven by a ledger: a dependency graph is not a tree, so reclamation
cannot recurse along dependencies. It runs in reverse entry order instead.

`init` / `start` / `stop` are three names for these two rules.

## Core concepts

| Name | What it is |
|---|---|
| `Canary` | The unit base class. Subclass it and you get four lifecycle actions. |
| `dep(Cls)` | A dependency declaration. You choose the attribute name. |
| `@init` / `@start` / `@stop` | Phase markers: which phase a method belongs to. |
| `Phase` | A phase itself. `Phase("migrate")` is a fourth one, no registration needed. |
| `Scope` | The state one run shares. One scope is one graph. |

## Invariants

1. **Units are always constructed with no arguments.** Anything that needs the outside world
   happens in a lifecycle hook, because only those have a matching reclamation step.
2. **One instance per type per scope.** Two separately constructed roots are two unrelated
   graphs.
3. **Dependencies exist from `@init` onward.** Reading one in `__init__` raises
   `LifecycleError`.
4. **Every `@init` completes before any `@start` runs.**
5. **`stop()` is the single reclamation path.** Success and failure share it, it is idempotent,
   and it leaves the graph ready to start again.

## Install

```bash
pip install canary-framework
```

Requires Python 3.12 or newer. Installing pulls in no third-party packages.

## Next

- [Why Canary](why-canary.md): where it fits, where it does not, and a measured comparison.
- [Quick Start](quickstart.md): a working example in ten minutes.
- [Units](canary.md): the four actions on `Canary`.
- [Dependencies](dependency-injection.md): `dep()` and scopes.
- [Lifecycle](lifecycle.md): phases, the barrier, failure and reclamation.
- [Patterns](patterns.md): test doubles, configuration, hosting, retry.
- [API Reference](api-reference.md): every public name.
- [Versioning & Compatibility](versioning.md): what 1.x promises.
