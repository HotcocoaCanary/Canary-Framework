# What's New in 0.9.3

0.9.3 is a **convergence**: it completes the failure paths, straightens out the mental model, and
removes the things that looked necessary but that any user can write themselves in ten lines. It
contains several breaking changes — 0.9.x is still taking shape.

## One rule that runs through everything

> **The framework only builds empty shells. Anything that needs input from outside happens in the
> lifecycle.**

Every instance on the graph is constructed **by the framework, with no arguments** — there is no
second source. This is not a restriction: a constructor has no counterpart (`@on_start` pairs with
`@on_stop`; "construction" has no "destruction"), so moving work that needs input into the
lifecycle puts every one of those steps into a phase that keeps a ledger and unwinds in reverse.

## Added

- **Injection moved to `init()`.** `@on_init` therefore has a meaning of its own for the first
  time — "dependencies are in place, nothing is running yet". Assembly errors now surface during
  assembly.
- **`ConstructionError`** — a unit that needs constructor arguments gets an actionable error
  instead of a bare `TypeError`, naming the single way out: turn the argument into a dependency.
- **`DeclarationError`** — `@get` on a plain `@cocoa` used to fail silently (the decorator
  applied, nothing was reported, the route simply was not there). It is now refused at assembly.
- **`InjectionError`** — two dependencies with the same snake_case name no longer let the last one
  win.
- **The assembly summary** — with `CANARY_LOG_LEVEL=DEBUG`, the end of startup prints the start
  order, dependencies and routes.
- **`CANARY_SLOW_CALLBACK_SECONDS`** — an optional event-loop lag probe that catches synchronous
  blocking inside `async def` bodies; restored on `stop()` so it never leaks into the rest of the
  process.
- **`status_code`** — `@post(..., status_code=201)`, `@delete(..., status_code=204)`. Previously
  this required building a `Response` by hand, which lost both return-type validation and the
  response schema in the document.
- **Documentation metadata** — `tags` (unit level and route level), `summary`, `deprecated`; the
  `description` comes straight from the handler's docstring.
- **Return-value validation** — a return value that does not match its annotation becomes a 500.
  `/docs` promises callers that shape, so the framework holds you to it.

## Changed (breaking)

- **`Canary(provide=...)` removed.** It contradicted the rule that units must be constructible
  with no arguments. Substituting a dependency in a test is plain attribute assignment
  (`svc.database = FakeDb()`) — injection never did more than that. `ProvisionError` is gone too.
- **`@on_request_error` and exception-mapping registration removed.** Exceptions now have three
  fixed outcomes: the request cannot bind → 422, `HTTPError` → its own status, anything else →
  a JSON 500. Expected business failures belong in the return value, not thrown for the framework
  to translate into a status code.
- **Prefixes no longer nest along the dependency chain.** `@web_cocoa(prefix=...)` is now an
  **absolute** prefix. Dependencies say what starts first; URLs say how resources are named —
  neither should decide the other. Want `/api/admin`? Write it out.
- **`Query` / `Path` / `Body` markers removed.** Inference (scalars → query, a name matching a
  placeholder → path, everything else → body) already gives the same answer. `Header` and `Cookie`
  stay — they are the only two sources inference cannot reach.
- **Parameter markers only inside `Annotated`.** `x: int = Query(10)` made the default-value
  position mean two things at once; it is now refused at assembly.
- **Handlers must be `async def`.** A synchronous handler stalls the whole process, not just its
  own request; the framework refuses at declaration time rather than silently offloading it.
- **`/redoc` removed.** One documentation UI is enough.
- **`stop()` is the single reclamation path.** Callable from any settled state and idempotent, so
  `finally: await app.stop()` is always safe.

## Fixed

- **A failing `start()` leaked started units.** It now keeps a ledger, unwinds in reverse
  (including the unit that failed), and re-raises the original exception.
- **A failing `@on_stop` aborted the whole shutdown.** Errors are now collected and raised at the
  end as an `ExceptionGroup`.
- **A failing lifespan startup hung the process.** After sending `lifespan.startup.failed` the
  error must be raised, or a caller implementing the protocol fully concludes the app started and
  hangs forever at shutdown. The same applies to shutdown failures.
- **Concurrent cold start without a lifespan crashed.** Five concurrent first requests used to
  produce one success and four `RuntimeError`s.
- **Every request-body failure became a 500.** An empty body, invalid JSON and a form post are all
  422 now, and `item: Item | None = None` (an optional body) finally works.
- **Constraints inside `Annotated` were silently dropped.** `Annotated[int, Field(gt=0)]` neither
  validated nor documented anything.
- **Two body parameters each received the whole body.** Refused at assembly now.
- **`prefix="api"` (no slash) raised a bare `AssertionError`.** Prefixes are normalised the same
  way route paths always were.
- **One undescribable type took down the whole OpenAPI document.** It degrades to "unconstrained"
  and logs a WARNING naming the handler **at startup**.
- **`{name:path}` converters leaked into the OpenAPI document.**
- **Handlers could not return a `Response`.** SSE, downloads, custom status codes and background
  tasks all work.
- **A validator raising `ValueError` turned its own 422 into a 500.**
- **The slow-callback probe could not see the startup phase.** asyncio reads the debug flag before
  a callback runs, and the probe was switched on inside `init()`.

## Performance

Signatures are compiled at assembly time into a value-fetching plan, so the request path does no
reflection at all — no `get_type_hints`, no `inspect.signature`, no `TypeAdapter` construction per
request:

```text
framework-only request path   125 us  →  16.5 us     ~7.5x
```

The same plan feeds OpenAPI generation, so dispatch and the document cannot drift apart.

## A core with zero dependencies

`pip install canary-framework` no longer pulls in anything third-party; starlette and pydantic
belong to the `[web]` extra.
