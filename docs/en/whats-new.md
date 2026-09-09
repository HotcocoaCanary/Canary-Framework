# What's New in 0.9.3

0.9.3 is a **convergence**: it pulls the framework back to the one thing it is actually different
at — **dependency assembly and lifecycle** — and completes the failure paths. It contains several
breaking changes, the largest of which is that the entire web extension is gone.

## What it is now

> **Canary is a runtime container, not a web framework.**

It assembles a set of objects according to their dependencies, starts them in order and reclaims
them in reverse. What shell eventually drives those objects — HTTP, a CLI, a scheduler, a message
consumer — is that shell's business.

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with canary:          # this is the whole wiring
        yield


app = FastAPI(lifespan=lifespan)
```

## One rule that runs through everything

> **The framework only builds empty shells. Anything that needs input from outside happens in the
> lifecycle.**

Every instance on the graph is constructed **by the framework, with no arguments** — there is no
second source. This is not a restriction: a constructor has no counterpart (`@on_start` pairs
with `@on_stop`; "construction" has no "destruction"), so moving work that needs input into the
lifecycle puts every one of those steps into a phase that keeps a ledger and unwinds in reverse.

## Removing `canary_framework.web`

**This is the headline change.** The web extension (`@web_cocoa`, route decorators, parameter
binding, OpenAPI — about 1300 lines) is gone, together with `Canary`'s ASGI surface (`__call__`,
the lifespan protocol, cold start, route collection — about 100 lines).

The reason is not that it was bad — its request path measured 2.4–3.3× faster than FastAPI. The
reason is that **it was not our job**:

- It did the same thing as FastAPI and Starlette, and that is not where this framework differs.
- Once on that road, you chase WebSocket, file uploads, middleware and auth forever.
- It was more than half the code and produced nearly all of the bugs.

And **the one thing it was protecting turns out not to need it**: routes as methods on a
dependency-injected unit works by handing the bound method straight to FastAPI — a bound method's
signature has no `self`, so FastAPI does the binding, validation and documentation as usual,
while `self.repo` is already there because Canary assembled the instance.

```python
unit = canary[LibraryApi]                       # a plain @cocoa, no web markers
app.get("/books/{book_id}")(unit.get_book)      # FastAPI takes it as-is
```

The framework went from 2300 lines to **842**, and every remaining line does dependency assembly
or lifecycle.

## Added

- **Assembly moved into the constructor; `init()` is gone.** When `Canary(Root)` returns the
  graph is built, sorted and injected — `canary[SomeUnit]` works immediately. This is the
  framework keeping its own rule ("a unit must be usable once constructed"); the runtime had no
  reason to be the exception.

  The seam now sits where the nature of the work changes: assembly is synchronous, deterministic
  and runs none of your runtime code; `start()` is the running part (every `@on_init`, then every
  `@on_start`). Assembly errors are raised on the line where you wrote `Canary(Root)`.

  The failure rules collapse from two into one: **`stop()` reclaims whatever is in the ledger.**
  The state machine went from 8 states to 6, and its start renamed `NEW` → `READY`.

- **`Canary.lifespan`** — the host-facing entry point; one line plugs it into any mainstream
  framework:

  ```python
  app = FastAPI(lifespan=canary.lifespan)
  app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
  server = MCPServer("demo", lifespan=canary.lifespan)
  ```

  Python has only two host shapes — take an async context manager, or take paired
  startup/shutdown callbacks — and both are now supported directly. `lifespan` differs from
  `async with canary` only in what it yields: `None` (the ASGI protocol treats the yielded value
  as a mapping to merge into `scope["state"]`, so yielding the container leaks a clueless
  `KeyError`) rather than the container itself.

- **Injection moved to `init()`.** `@on_init` therefore has a meaning of its own for the first
  time — "dependencies are in place, nothing is running yet".
- **`ConstructionError`** — a unit that needs constructor arguments gets an actionable error
  naming the single way out: turn the argument into a dependency.
- **`InjectionError`** — two dependencies whose snake_case names collide no longer let the last
  one win.
- **The assembly summary** — with `CANARY_LOG_LEVEL=DEBUG`, the end of startup prints the start
  order and each unit's dependencies.
- **`CANARY_SLOW_CALLBACK_SECONDS`** — an optional event-loop lag probe that catches synchronous
  blocking inside `async def` bodies; restored on `stop()`.

## Changed (breaking)

- **`canary_framework.web` and `Canary`'s ASGI surface removed** (see above). `Canary` is no
  longer an ASGI app; plug it into a host with `async with canary:`.
- **`Canary(provide=...)` removed.** It contradicted "units are always constructed with no
  arguments". Substituting a dependency in a test is plain attribute assignment
  (`svc.database = FakeDb()`) — injection never did more than that.
- **`stop()` is the single reclamation path.** Callable from any settled state and idempotent, so
  `finally: await app.stop()` is always safe.

## Fixed

- **A failing `start()` leaked started units.** It now keeps a ledger and unwinds in reverse
  (including the unit that failed) before re-raising the original exception.
- **A failing `@on_stop` aborted the whole shutdown.** Errors are collected and raised at the end
  as an `ExceptionGroup`.
- **A dependency chain of ~1000 hit `RecursionError`.** How deep a chain goes is the user's data,
  not something Python's recursion limit should bound. The graph is now built with an explicit
  stack; 50 000 links work fine.
- **The slow-callback probe could not see the startup phase.** asyncio reads the debug flag
  before a callback runs, and the probe was switched on halfway through one.

## Performance

```
1000 units: build + inject + @on_init    37.7ms → 2.4ms      15.6x
MRO scan (5000 units, self time)          55ms  → 5ms        11x
the framework's own import cost                            0.0ms
a 1000-unit graph                                       ~3.9 MiB
```

That 15.6× came from one inverted order: `inspect.signature` sat on the **success** path while
existing only to explain failures. It now constructs first and inspects the signature only after
a `TypeError`.

## Zero dependencies

`pip install canary-framework` pulls in nothing but the standard library. A test guards it: after
a full lifecycle, nothing from site-packages may appear in `sys.modules`.
