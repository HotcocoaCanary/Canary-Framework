# What's New in 1.2

1.2 adds four extension packages beside the core. The core itself has two fixes; the first
changes what one way of writing a subclass does, so it comes first. Nothing else needs
changing.

For earlier releases, see [What's New in 1.1](whats-new-1.1.md) and
[What's New in 1.0](whats-new-1.0.md).

## Behaviour fix: overriding a dependency by name replaces it

Dependencies now resolve by attribute name, as hooks already did. Write another `dep()` under
the same name in a subclass and the base class's is replaced:

```python
class Service(Canary):
    store = dep(SqlStore)


class TestService(Service):
    store = dep(MemoryStore)    # 1.1: SqlStore was still built and started. 1.2: only MemoryStore.
```

Override the name with something that is not a `dep()` and the dependency is dropped. If your
code relied on the old behaviour — expecting the base class's dependency to start in the
subclass as well — give it an attribute name of its own.

## Extension packages

Four extensions ship with the core and share its version number. The core imports none of
them, and `import canary_framework` still loads no third-party package; install the ones you
use.

| Package | What it is | Install |
|---|---|---|
| [`canary_framework.test`](extensions/test.md) | Start a graph on test doubles; reach a unit by type | with the core |
| [`canary_framework.config`](extensions/config.md) | pydantic-settings configuration that is also a unit | `canary-framework[config]` |
| [`canary_framework.web.asgi.app`](extensions/app.md) | Application units: a small web framework | `canary-framework[app]` |
| [`canary_framework.web.asgi.server`](extensions/server.md) | The server unit: listening as part of the lifecycle | `canary-framework[server]` |

`canary-framework[web]` installs both the application and the server side.

They are **provisional** for now: until each is declared stable its API may change in a minor
release; see [Versioning & Compatibility](versioning.md#extensions).

### An example

```python
from canary_framework import dep
from canary_framework.config import Settings
from canary_framework.test import running
from canary_framework.web.asgi.app import App, Router, get
from canary_framework.web.asgi.server import Server


class AppConfig(Settings):
    greeting: str = "hello"


class ReaderApi(Router, prefix="/readers"):
    config = dep(AppConfig)

    @get("/{reader_id}")
    async def show(self, reader_id: int) -> Reader:
        return Reader(id=reader_id, name=self.config.greeting)


class LibraryApi(App):
    readers = dep(ReaderApi)


class Gateway(Server):
    api = dep(LibraryApi)
    port = 8010


async with Gateway():                   # binding the port is @start, closing it is @stop
    ...

async with running(Gateway, {AppConfig: AppConfig(greeting="hi")}) as gateway:
    ...                                 # a test: the whole graph on another configuration
```

Routers and the application are units, and dependencies are `dep()`. An application unit is
itself an ASGI application, so it also runs without `Server` — `uvicorn main:app` — and
`Server` in turn serves any ASGI application, a FastAPI object included.

Application units generate no OpenAPI, but `App.endpoints` exposes the flattened endpoint
table, from which writing one takes a few dozen lines; see
[Web Application › The endpoint table](extensions/app.md#endpoints).

## Also in 1.2

- `Scope.entered(phase)` always lists dependencies first. Calling `stop()` on a graph that
  had been initialised but never started used to leave it root first after the next
  `start()`.
- Two new sections in [Patterns](patterns.md):
  [Several instances of one kind](patterns.md#several-instances-of-one-kind) and
  [Shutting down in two steps](patterns.md#two-step-shutdown).
- `benchmarks/web.py` load-tests the same endpoints written as application units and as
  FastAPI, scenario by scenario.
- Development: the `dev` extra now pulls in the extensions' dependencies, and a new `test`
  extra holds only what the core's tests need; CI also runs the core's tests in an
  environment without those dependencies.
- The full list is in the
  [changelog](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md).
