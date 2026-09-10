# What's New in 0.9.3

0.9.3 contains several breaking changes; 0.9.x is still taking shape.

## Lifecycle

Four actions, each running exactly one phase:

```python
canary = Canary(Root)      # assembly: build, sort, inject. Synchronous, runs no hooks
await canary.init()        # every @on_init
await canary.start()       # every @on_start
await canary.stop()        # every @on_stop, in reverse
```

- **Assembly moved into the constructor.** When `Canary(Root)` returns, the graph is built,
  sorted and injected, and `canary[SomeUnit]` works immediately; assembly errors
  (`ConstructionError`, `InjectionError`, `CircularDependencyError`, `TypeError` for a
  non-cocoa) are raised on that line.
- **`init()` runs only `@on_init`; `start()` runs only `@on_start`.** Between them is a barrier:
  every `@on_init` completes before any `@on_start` runs. Calling `start()` without `init()`
  raises `LifecycleError: call init() before start()`.
- **`stop()` is the single reclamation path** — callable from `STARTED` and from `FAILED`,
  idempotent, a no-op when nothing ever started. One failure rule: `stop()` reclaims whatever is
  in the ledger.
- **The starting state is `READY`** (previously `NEW`).

## Concurrent startup

```python
Canary(Root, start_concurrency=8)
```

Independent units start together, at most N at once. Scheduling is dependency-driven, so the
elapsed time tracks the graph's critical path. The default, `None`, is strictly sequential.
Failure semantics match sequential startup: a lone failure is re-raised as-is, several
simultaneous failures become an `ExceptionGroup`, and cancelled units are still reclaimed.

On a sequential startup, the `CANARY_LOG_LEVEL=DEBUG` assembly summary records per-unit timings,
computes the critical path and suggests a `start_concurrency` value.

## Plugging into a host

```python
app = FastAPI(lifespan=canary.lifespan)              # ASGI, MCP, FastStream
app = Litestar(route_handlers=[...], lifespan=[canary.lifespan])
async with canary.lifespan(): ...                    # no host
```

Hosts taking paired startup/shutdown callbacks (Quart, Sanic, arq, Dramatiq) use `init()` /
`start()` and `stop()`.

## Added

- `ConstructionError` — an actionable error when a unit needs constructor arguments, instead of
  a bare `TypeError`.
- `InjectionError` — raised when two dependencies produce the same snake_case name, instead of
  the last one silently winning.
- The assembly summary — with `CANARY_LOG_LEVEL=DEBUG`, the end of startup prints the start
  order plus each unit's dependencies and timing.
- `CANARY_SLOW_CALLBACK_SECONDS` — an event-loop lag probe that catches synchronous blocking
  inside `async def` bodies; restored on `stop()`.

## Removed

- The `canary_framework.web` extension and `Canary`'s ASGI surface (`__call__`, the lifespan
  protocol, cold start, route collection). `Canary` is no longer an ASGI app.
- `Canary(provide=...)` and `ProvisionError`. Substituting a dependency in a test is plain
  attribute assignment.
- The `[web]` and `[test]` extras.

## Fixed

- A failing `start()` leaked started units — it now unwinds the ledger in reverse before
  re-raising the original exception.
- A failing `@on_stop` aborted the whole shutdown — errors are now collected and raised at the
  end as an `ExceptionGroup`.
- A dependency chain of ~1000 hit `RecursionError` — the graph is built with an explicit stack,
  and 50 000 links work fine.
- The slow-callback probe could not see the startup phase.

## Performance

```
assembling 1000 units (build + inject)   37.7ms → 2.4ms
MRO scan (5000 units, self time)          55ms  → 5ms
the framework's own import cost                    0.0ms
a 1000-unit graph, resident                    ~3.9 MiB
```

## Zero dependencies

`pip install canary-framework` uses nothing but the standard library. A test guards it: after a
full lifecycle, no module from site-packages appears in `sys.modules`.
