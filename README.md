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

**Entering** runs dependencies first: a unit enters a phase only after its dependencies have
completed it. One unit runs one phase exactly once no matter how many units depend on it, and
independent units enter concurrently.

**Releasing** runs the unit first: stopping a unit stops it — unless something still uses it —
then tries its dependencies the same way, so what nothing else uses goes down with it. A failed
`start()` releases what it brought up before it raises.

Both run on the dependency graph, built before any hook runs — which is also where cycles are
caught.

`init` / `start` / `stop` are three names for these two rules. Adding a fourth phase is one
line: `Phase("migrate", after=init)`.

## Highlights

- **Typed end to end.** `self.config` is a `Config`, `async with service` yields your type, and
  `dep(SomethingElse)` is a type error. No plugin required.
- **Plain classes.** Decorators only mark methods; units stay subclassable, mixable, nestable,
  and lifecycle methods can be overridden with `super()`.
- **Failure paths are part of the design.** A failing `start()` releases what it started; `stop()`
  is the single reclamation path, shared by success and failure, and is idempotent. A stopped
  graph starts again; a failed enter can be retried.
- **Test doubles without mocks.** `scope_of(service).provide(Database, FakeDatabase())` swaps a
  dependency across the whole graph, and the double runs its own lifecycle.
- **Concurrent by default.** Independent units start together and stop together, scheduled by
  the dependency graph.
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

## Extensions

Four optional packages sit beside the core. The core never imports them, so
`pip install canary-framework` stays dependency-free.

| Package | What it is | Install |
|---|---|---|
| [`canary_framework.test`](https://hotcocoacanary.github.io/Canary-Framework/extensions/test/) | `running()` and `unit()` — start a graph on test doubles | included |
| [`canary_framework.config`](https://hotcocoacanary.github.io/Canary-Framework/extensions/config/) | `Settings` — a pydantic-settings model that is a unit | `canary-framework[config]` |
| [`canary_framework.asgi`](https://hotcocoacanary.github.io/Canary-Framework/extensions/asgi/) | `App` and `Server` — applications are units, and one server listens for those it depends on | `canary-framework[asgi]` |
| [`canary_framework.asgi.fastapi`](https://hotcocoacanary.github.io/Canary-Framework/extensions/fastapi/) | `Router` and `App` — FastAPI routes on units | `canary-framework[fastapi]` |

```python
from canary_framework import asgi, dep
from canary_framework.asgi.fastapi import App, Router, get


class ReaderApi(Router, prefix="/readers"):
    readers = dep(ReaderService)

    @get("/{reader_id}")
    async def get(self, reader_id: int) -> Reader:
        return await self.readers.get(reader_id)


class LibraryApi(App, title="Library API"):
    readers = dep(ReaderApi)


class Gateway(asgi.Server):
    api = dep(LibraryApi)  # another App unit here would share the port
    port = 8010


async with Gateway():  # dependencies start, then it listens
    ...
```

Extensions are provisional: their API may still change in a minor release.

## Stability

1.0 is the first stable release. The public API follows
[Semantic Versioning](https://hotcocoacanary.github.io/Canary-Framework/versioning/): no
breaking changes before 2.0, and removals are deprecated for at least one minor release first.

## Documentation

- [Why Canary](https://hotcocoacanary.github.io/Canary-Framework/why-canary/) — where it fits,
  where it does not, and a measured comparison with dishka, dependency-injector, injector and
  FastAPI `Depends`
- [Documentation](https://hotcocoacanary.github.io/Canary-Framework/) —
  [What's new in 1.1](https://hotcocoacanary.github.io/Canary-Framework/whats-new/),
  [patterns](https://hotcocoacanary.github.io/Canary-Framework/patterns/),
  [upgrading from 0.9.x](https://hotcocoacanary.github.io/Canary-Framework/upgrading-from-0.9/)
- Complete examples — a FastAPI service and a long-running daemon:
  [Canary-Framework-Example](https://github.com/HotcocoaCanary/Canary-Framework-Example)
  (checked out at [`examples/`](examples) as a submodule)

## Community

Questions and ideas go to [Discussions](https://github.com/HotcocoaCanary/Canary-Framework/discussions),
bugs to [Issues](https://github.com/HotcocoaCanary/Canary-Framework/issues). See
[CONTRIBUTING](CONTRIBUTING.md), [GOVERNANCE](GOVERNANCE.md) and [SECURITY](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
