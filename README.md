<h1 align="center">Canary Framework</h1>

<p align="center">
  <strong>Dependency injection</strong> and <strong>lifecycle</strong> for plain Python
  classes &mdash; standard library only, zero dependencies.
</p>

<p align="center">
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/HotcocoaCanary/Canary-Framework/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="PyPI" src="https://img.shields.io/pypi/v/canary-framework.svg"></a>
  <a href="https://pypi.org/project/canary-framework/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/canary-framework.svg"></a>
  <a href="https://github.com/HotcocoaCanary/Canary-Framework/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/canary-framework.svg"></a>
</p>

<p align="center">
  <a href="README_ZH.md">中文</a> ·
  <a href="https://hotcocoacanary.github.io/Canary-Framework/">Documentation</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

## Install

```bash
pip install canary-framework
```

Requires Python 3.12 or newer. Installing pulls in no third-party packages.

## The model

Subclass `Canary` and you have a **unit**: it declares what it depends on with `dep()`, and
what it does in each phase with `@init` / `@start` / `@stop`. Start one unit and its
dependencies come up in dependency order; leaving reclaims them in reverse.

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

```
connecting to postgresql://localhost/dev
postgresql://localhost/dev
disconnected
```

## Two rules

**Advancing** recurses along dependencies: a unit enters a phase only after its dependencies
have completed it. One unit runs one phase exactly once no matter how many units depend on it,
and independent dependencies advance concurrently.

**Unwinding** is linear: a dependency graph is not a tree, so reclamation runs over a ledger in
reverse entry order.

`init` / `start` / `stop` are three names for these two rules. Adding a fourth phase is one
line: `Phase("migrate", after=init)`.

## Highlights

- **Typed end to end.** `self.config` is a `Config`, `async with service` yields your type, and
  `dep(SomethingElse)` is a type error. No plugin required.
- **Plain classes.** Decorators only mark methods; units stay subclassable, mixable, nestable,
  and lifecycle methods can be overridden with `super()`.
- **Failure paths are part of the design.** A failing `start()` reclaims what started; `stop()`
  is the single reclamation path, shared by success and failure, and is idempotent.
- **Concurrent by default.** Independent units advance together, scheduled by dependency.
- **Zero dependencies.** A test asserts that a full lifecycle imports nothing from
  site-packages.

## Hosting

The framework knows nothing about shells — HTTP, CLI, schedulers and consumers are all yours:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:
        yield


app = FastAPI(lifespan=lifespan)
```

## Documentation

Full documentation, including migration from 0.9.x, is at
[hotcocoacanary.github.io/Canary-Framework](https://hotcocoacanary.github.io/Canary-Framework/).

A complete five-layer example lives in [`examples/library/`](examples/library).

## License

Apache-2.0. See [LICENSE](LICENSE).
