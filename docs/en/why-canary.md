# Why Canary

Canary does one thing: it wires application-lifetime objects together and runs their startup
and shutdown. This page says where that fits, where it does not, and how it compares with other
Python libraries.

Every row in the comparison below is measured, not recalled:
[`benchmarks/comparison.py`](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/benchmarks/comparison.py)
builds the same small graph with each library and prints the results. Run it yourself:

```bash
uv run benchmarks/comparison.py
```

Measured on 2026-09-23 with Python 3.13; library versions are pinned in the script's header.

## Where Canary fits

- **Async services, daemons and workers** whose long-lived objects hold resources — connection
  pools, clients, background tasks — and must come up and go down in dependency order.
- **Startup and shutdown as part of the object.** A unit carries its `@start` / `@stop` hooks; the
  graph comes up concurrently where it can, rolls back what it acquired when startup fails, and
  can start again after `stop()`. Further phases are one line: `Phase("migrate", after=init)`.
- **Typed attributes instead of lookups.** `self.db` is a `Database` to the type checker, with no
  container call and no annotation to repeat.

## Where it does not

- **Request-scoped objects.** Canary has one instance per type per graph and no request scope.
  Use your web framework for per-request values — FastAPI's `Depends` combines well with Canary,
  see below — or a library with scopes such as dishka.
- **Domain classes that must not know about a framework.** Units subclass `Canary`. dishka,
  dependency-injector and injector wire plain classes through their `__init__` instead.
- **Several instances of one type, or constructor arguments.** Units are constructed with no
  arguments, one per type; values come from dependencies in `@init` or `@start`.
- **Synchronous programs.** `init()`, `start()` and `stop()` are coroutines. Hooks may be
  synchronous, but something has to run an event loop.
- **Maturity.** Canary is young and has one maintainer. The others have larger communities and
  ready-made integrations for web frameworks.

## Comparison

The scenario: `Config`, two independent resources `Database` and `Cache` that each take 0.1 s to
acquire, and a `Service` that needs both.

| | Canary 1.1.0 | dishka 1.10.1 | dependency-injector 4.49.1 | injector 0.24.0 | FastAPI `Depends` 0.141.1 |
|---|---|---|---|---|---|
| Wiring | `dep()` attributes on the class | `Provider` classes | a container of providers | modules and binders | `Depends(...)` in handler signatures |
| Your classes | subclass `Canary` | plain classes | plain classes | plain classes, `@inject` on `__init__` | plain functions |
| Type from `mypy --strict` | `svc.db` is `Database` | `get(Service)` is `Service` | `service()` is `Service`¹ | `get(Service)` is `Service` | from the parameter annotation |
| Acquire and release | `@start` / `@stop` hooks | async generator factories | `Resource` providers | — | generator dependencies |
| Two independent resources | **0.10 s**, concurrent | 0.20 s, sequential | **0.10 s**, concurrent | — | 0.20 s, per request |
| Dependent resources released in reverse | yes | yes | yes | — | yes, per request |
| A failure midway through startup | **released before the exception reaches you** | released on `close()` | released on `shutdown_resources()` | — | per request |
| Start again after shutdown | yes | yes | yes | — | — |
| Replace a dependency in tests | `scope_of(root).provide(...)` | a later `Provider` | `provider.override(...)` | `binder.bind(...)` | `app.dependency_overrides` |
| Per-request or context scope | **no** | `Scope.REQUEST` | `ContextLocalSingleton` | `threadlocal` | per request by default |
| Third-party packages installed | 0 | 0 | 0 | 0 | 9 |

¹ When any resource in the chain is async, `service()` returns an awaitable at runtime while its
static type is still `Service`; and under `--strict`, `await container.init_resources()` is
reported as an error because it is typed `Awaitable[None] | None`.

What the table does and does not say:

- **Timings** come from resources that sleep for 0.1 s. They show whether independent resources
  are acquired concurrently, not how fast each library is.
- **Failure midway through startup.** In every library with a lifecycle, what was acquired gets
  released. The difference is who triggers it: Canary rolls back inside `start()`, so a caller
  that only sees the exception has nothing left to clean up; with dishka and dependency-injector
  the caller releases by calling `close()` / `shutdown_resources()`, typically in a `finally`.
- **injector** has no lifecycle API, so the lifecycle rows do not apply.
- **FastAPI `Depends`** is request-scoped: both resources are acquired and released on every
  request. Objects that live as long as the application go in the app's `lifespan`, which you
  write yourself.
- **Zero dependencies is not unique to Canary.** dishka, dependency-injector and injector install
  nothing else either.

## Canary with FastAPI

The two do different jobs and combine without friction: Canary owns what lives as long as the
application, and `Depends` hands per-request values to handlers.

```python
service = LibraryService()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with service:          # the whole graph comes up, and is reclaimed on shutdown
        yield


app = FastAPI(lifespan=lifespan)


def books() -> BookRepository:
    return service.books         # an application-lifetime unit


@app.get("/books/{book_id}")
async def get_book(book_id: int, repo: Annotated[BookRepository, Depends(books)]):
    ...
```

[Canary-Framework-Example](https://github.com/HotcocoaCanary/Canary-Framework-Example) has the
complete version, with tests: the `library` project is a FastAPI service built this way.
