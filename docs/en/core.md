# Architecture & Internals

This page covers the internal design, data flow, and mechanics of Canary Framework. It is the
deep-dive companion to the task-oriented guides — for usage patterns see
[Services](services.md), [Modules](modules.md), [Dependency Injection](dependency-injection.md),
[Lifecycle](lifecycle.md), and [Web & Routing](web.md).

!!! info "Post-redesign router model"
    The routing subsystem was rebuilt around **single-point memoized assembly**. If you remember
    the old model (duck-typed mounts, per-service `asgi_app` overrides, docs generated on
    `startup()`, mount-at-`/{ServiceName}`), discard it — every one of those mechanisms is gone.
    This page documents the current source only.

## Layer architecture { #layers }

The package (`src/canary_framework/`) is strictly layered. Imports only ever flow **downward**:

```
common/       zero internal deps — types, config, errors, logging
   ↓
engine/       registry, dependency resolution + topological sort, openapi, params
   ↓
core/         ServiceBase, ModuleBase, Router (the base classes users subclass)
   ↓
decorators/   @service, @module, @config, @before_startup, @before_shutdown
```

- **`common/`** — Zero framework-internal dependencies. Shared enums and dataclasses
  (`RouteInfo`, `ResolvedRoute`, `ServiceMeta`, `ModuleMeta`), the `CanaryConfig` model, the error
  hierarchy, and logging. Everything else may import it.
- **`engine/`** — Runtime machinery that depends only on `common/`: the `Registry`,
  dependency resolution + topological sort (`dependencies.py`), OpenAPI schema generation
  (`openapi.py`), and parameter resolution (`params.py`).
- **`core/`** — The classes users subclass: `ServiceBase`, `ModuleBase`, and the `Router` route
  manager. This is where lifecycle, DI wiring, route collection, and ASGI integration live.
- **`decorators/`** — The public API surface: `@service`, `@module`, `@config`, `@before_startup`,
  `@before_shutdown`. Decorators validate base-class inheritance and attach metadata markers.

!!! note "Where `engine` sits"
    `engine/` is imported **by** `core/`, so it sits *above* `core` in the dependency graph — a
    common point of confusion. Nothing in `engine/` imports from `core/` or `decorators/`.

## ServiceBase internals { #servicebase }

`ServiceBase` (`core/service/_base.py`) is the root base class for all framework components;
`ModuleBase` inherits from it. It is itself an ASGI application and owns the entire route-assembly
pipeline. The `Router` is a separate route manager attached as a class attribute.

### Instance state { #servicebase-init }

`__init__` sets up three lazily-populated fields and nothing else:

```python
def __init__(self) -> None:
    self._cf_hooks: HookDict | None = None          # discovered on first hook invocation
    self._cf_parent_registry: object | None = None  # set by the parent module during init
    self._cf_assembled: Assembled | None = None      # memoized assembly result
    super().__init__()
```

`Assembled` is a `NamedTuple` carrying the two products of assembly:

```python
class Assembled(NamedTuple):
    router: StarletteRouter        # the built routing table
    openapi: dict[str, object]     # the OpenAPI document
```

### Route collection { #servicebase-collect-routes }

`_cf_collect_routes()` returns this node's **route contribution** as a `list[ResolvedRoute]`:

```python
def _cf_collect_routes(self) -> list[ResolvedRoute]:
    router = self._get_router()          # the `router` class attribute, if it is a Router
    if router is None:
        return []
    out = []
    for info in router._route_infos:
        bound = info.handler.__get__(self, type(self))   # bind the handler to this instance
        full_path = router.prefix + info.starlette_path  # compose the prefix
        while "//" in full_path:                          # normalize repeated slashes
            full_path = full_path.replace("//", "/")
        out.append(ResolvedRoute(full_path=full_path, handler=bound, info=info))
    return out
```

Each `ResolvedRoute` is the **aggregation currency**: a `full_path` (prefix already composed), a
`handler` already bound to its owning instance, and the original `RouteInfo`. A service with no
`Router` contributes an empty list.

### Single-point assembly { #servicebase-assemble }

`_cf_assemble()` is the heart of the redesign. Whichever node you run — a standalone `@service` or
a top-level `@module` — goes through this **one** method:

```python
def _cf_assemble(self) -> Assembled:
    resolved = self._cf_collect_routes()          # 1. collect the whole subtree
    if not resolved:
        return Assembled(StarletteRouter([]), {})
    _check_route_collisions(resolved)             # 2. reject duplicate (method, full_path)
    cfg = self.config or CanaryConfig()
    routes = [_build_route(r) for r in resolved]  # 3a. build one Starlette routing table
    openapi = generate_openapi_schema(resolved, ...)   # 3b. build one OpenAPI doc
    routes += _build_doc_routes(openapi, ...)     # 3c. add /openapi.json, /docs, /redoc
    return Assembled(StarletteRouter(routes), openapi)
```

The data flow, end to end:

```
_cf_collect_routes()  →  list[ResolvedRoute]         (whole subtree, prefixes composed)
        │
        ├─►  _check_route_collisions   →  ValueError on duplicate (method, full_path)
        │
        ├─►  _build_route (per route)  →  Starlette Route table
        │
        └─►  generate_openapi_schema   →  OpenAPI dict  ─►  _build_doc_routes  →  doc endpoints
                                                                    │
                       StarletteRouter(routes + doc routes)  ◄──────┘
                                    │
                            Assembled(router, openapi)   (cached in self._cf_assembled)
```

The result is cached in `self._cf_assembled`, so assembly runs **at most once** per node.

!!! tip "standalone == mounted"
    This is the central simplification. A lone service run directly and the *same* service composed
    inside a module serve **identical paths** — because both paths run this one `_cf_assemble`. The
    only difference is the scope of the subtree `_cf_collect_routes()` walks. Doc endpoints are
    built **once**, at whichever node you actually run.

### `asgi_app` and `openapi()` { #servicebase-asgi-openapi }

Both accessors trigger (and share) the memoized assembly:

```python
@property
def asgi_app(self) -> StarletteRouter:
    if self._cf_assembled is None:
        self._cf_assembled = self._cf_assemble()
    return self._cf_assembled.router

def openapi(self) -> dict[str, object]:
    if self._cf_assembled is None:
        self._cf_assembled = self._cf_assemble()
    return self._cf_assembled.openapi
```

`openapi()` is a public accessor for the assembled OpenAPI document. Assembly is **lazy** — it
happens on the first `asgi_app`/`openapi()` access, which is always *after* `init()` has wired the
subtree.

### `__call__` — the ASGI entry point { #servicebase-call }

`ServiceBase` is an ASGI app. `__call__` does exactly two things:

```python
async def __call__(self, scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await self._handle_lifespan(receive, send)   # lifespan → startup/shutdown
    else:
        await self.asgi_app(scope, receive, send)    # everything else → assembled router
```

`_handle_lifespan` implements the ASGI lifespan protocol: a `lifespan.startup` message calls
`self.startup()` then acks with `lifespan.startup.complete`; a `lifespan.shutdown` message calls
`self.shutdown()`, acks, and returns.

### Lifecycle methods { #servicebase-lifecycle }

| Method       | Kind  | What it does |
|--------------|-------|--------------|
| `init()`     | sync  | Base implementation just logs. `ModuleBase` overrides it to wire the subtree. |
| `startup()`  | async | Invokes the `BEFORE_STARTUP` hook via `_invoke_hook`. |
| `shutdown()` | async | Invokes the `BEFORE_SHUTDOWN` hook via `_invoke_hook`. |

!!! warning "startup() no longer builds anything"
    In the old model `startup()` generated the OpenAPI schema and registered doc endpoints. It no
    longer does. All routing and documentation are produced by `_cf_assemble` on first
    `asgi_app`/`openapi()` access. `startup()` only fires hooks.

### `_invoke_hook` { #servicebase-invoke-hook }

On first call, `_invoke_hook` discovers hooks via `find_hooks()` (`core/service/_hooks.py`), which
walks the class MRO for methods carrying the hook markers (`__cf_before_startup__`,
`__cf_before_shutdown__`) and binds them to the instance. The result is cached in `_cf_hooks`. If no
hook is registered for the phase it returns silently; a coroutine hook is awaited, a plain hook is
called directly; any exception raised by a hook is wrapped in `LifecycleHookError`.

## ModuleBase internals { #modulebase }

`ModuleBase` (`core/module/_base.py`) extends `ServiceBase` and orchestrates child services. It
**inherits** `_cf_assemble`, `asgi_app`, and `openapi()` unchanged — there is no module-specific
ASGI override. A module differs from a plain service only in `__init__`, `init()`, its
`_cf_collect_routes` override, and lifecycle propagation.

### `__init__` { #modulebase-init-state }

`ModuleBase.__init__` calls `super().__init__()`, then adds registry/order fields and instantiates
config **immediately** so `log_level` takes effect before anything else runs:

```python
super().__init__()
self._cf_registry: Registry | None = None
self._cf_startup_order: list[str] = []
self._cf_config: CanaryConfig | None = None

meta = get_module_meta(type(self))
if meta is not None and meta.config_cls is not None:
    self._cf_config = meta.config_cls()
    ensure_logging(self._cf_config.log_level)
else:
    ensure_logging("INFO")
```

### `init()` flow { #modulebase-init-flow }

`init()` is synchronous and runs the whole composition pass:

```
reset _cf_assembled  (discard any pre-init cached assembly)
        ↓
register services recursively   (_register_entry_with_deps → resolve_deps, transitive)
        ↓
topological_sort                (Kahn's algorithm → startup order)
        ↓
instantiate + DI-wire           (entry.cls(); _wire_service; propagate registry + config)
        ↓
init each child                 (child.init() in topological order)
```

Step by step:

1. **Reset the cache.** `self._cf_assembled = None` first, so any assembly memoized *before*
   `init()` (which would have seen an empty registry) can't poison later `asgi_app`/`openapi()`
   access.
2. **Register.** `_register_entry_with_deps` registers each class in `meta.services`, then walks
   `resolve_deps(cls)` to register every transitive dependency. Classes decorated neither
   `@service` nor `@module` raise `TypeError`.
3. **Topologically sort** via `topological_sort` (see [below](#topological-sort)).
4. **Instantiate and wire, in one topological pass.** For each name: `entry.cls()`, then
   `_wire_service(inst, registry)` does `setattr(inst, attr, dep_instance)` for each resolved
   dependency. Every `ServiceBase` child gets `_cf_parent_registry` set and inherits the module's
   `_cf_config` if it has none of its own. The module itself is then wired with `_wire_service(self, registry)`.
5. **Init children.** Each child's `init()` is called in topological order, then `super().init()`.

### Module route contribution { #modulebase-collect-routes }

`ModuleBase` overrides `_cf_collect_routes` to **fold** its own contribution together with every
child's — a flat concatenation, with **no prefix cascade** (each node already owns its own prefix):

```python
def _cf_collect_routes(self) -> list[ResolvedRoute]:
    out = list(super()._cf_collect_routes())        # the module's own routes
    for _, child in self._iter_instances(skip_none=True):
        collect = getattr(child, "_cf_collect_routes", None)
        if collect is not None:
            out.extend(collect())                    # each child's contribution, as-is
    return out
```

Because assembly (`_cf_assemble`) is inherited from `ServiceBase` and consumes exactly this list,
a module and a service assemble their routing tables through identical code.

### Lifecycle propagation { #modulebase-lifecycle }

All three phases propagate over children:

- **`init()`** — synchronous; children in topological order (after registration + wiring above).
- **`startup()`** — async; fires the module's own `BEFORE_STARTUP` hook (via `super().startup()`),
  then awaits each child's `startup()` in **topological order**.
- **`shutdown()`** — async; fires `BEFORE_SHUTDOWN`, then awaits each child's `shutdown()` in
  **reverse** topological order.

## Router internals { #router }

`Router` (`core/router/_base.py`) is a standalone route manager — **not** a `ServiceBase` subclass.
It is used as a class attribute on a `@service` or `@module` class:

```python
router = Router(prefix="/users", tags=["users"])
```

### Constructor and storage { #router-constructor }

```python
Router(prefix: str = "", *, tags: list[str] | None = None)
```

- `prefix` — URL prefix composed onto every route in this router (e.g. `"/api/v1"`).
- `tags` — OpenAPI tags auto-applied to every endpoint under this router.

Internally the router stores `self._route_infos: list[RouteInfo]`. It holds **data**, not runtime
routes — nothing is bound or built until assembly.

### HTTP method decorators { #router-decorators }

`@router.get / .post / .put / .delete / .patch` all delegate to `_http_method`, which:

1. Parses the path with `parse_route_path(path)` → `(starlette_path, path_params, query_params)`.
   Query params come from the `?a={a}&b={b}` portion of the path string.
2. Resolves handler parameter types via `resolve_params(fn)` into `param_meta`.
3. Auto-detects the request body: the first handler parameter that is neither a path nor a query
   param — if annotated with a `BaseModel` subclass (or an explicit `request_model=` is given) —
   becomes `request_model`, and its name is recorded as `body_param`.
4. Constructs a `RouteInfo` and appends it to `self._route_infos`.

The decorator returns the original function unchanged (no wrapping).

Accepted decorator kwargs: `summary`, `description`, `response_model`, `request_model`, `tags`,
`deprecated`, `operation_id`, `responses`. (There are no `path_params` / `query_params` kwargs —
they are derived from the path string.)

### From `RouteInfo` to Starlette routes { #router-build }

Router stores `RouteInfo`s; assembly turns them into `ResolvedRoute`s
([`_cf_collect_routes`](#servicebase-collect-routes)) and then into Starlette `Route`s via
`_build_route` (`core/router/_utils.py`). `_build_route` creates an `endpoint` closure that:

- Binds each **path param** from `request.path_params` with type coercion; a coercion failure
  returns **400**.
- Binds each **query param** from `request.query_params` with coercion; an invalid value or a
  missing required param returns **422**.
- If a `request_model` + `body_param` are set, reads `await request.json()` (invalid JSON → **400**)
  and validates with the Pydantic model (`ValidationError` → **422**), passing the model to the body
  param.
- Calls `await handler(**kwargs)` and converts the return value via `_auto_response`.

### Collision detection { #router-collisions }

`_check_route_collisions(resolved)` runs during assembly over the *whole* collected subtree. It
tracks a `set` of `(method, full_path)` pairs and raises `ValueError` on the first duplicate:

```python
raise ValueError(f"Route collision: {r.info.method} {r.full_path}")
```

!!! warning "Explicit prefixes — no auto-namespacing"
    There is **no** `/{ServiceName}` auto-mount. A service with no prefix serves at the bare route
    path. To namespace a service, give its router an explicit `prefix` (e.g.
    `Router(prefix="/users")`). Two services that would serve the same `(method, full_path)` across
    the composed tree collide at assembly time and raise `ValueError`.

## Dependency injection flow { #di }

```
resolve_deps(cls)  →  get_type_hints(cls)  →  keep only types carrying CF_SERVICE_MARKER
        ↓
{attr_name: dep_type}
        ↓
recursive registration  →  topological_sort (Kahn)
        ↓
startup order: [name1, name2, ...]
        ↓
instantiate  →  setattr injection (_wire_service)  →  lifecycle
```

Dependencies are declared as **bare class-level type annotations**, not constructor arguments:

```python
@service()
class Auth(ServiceBase):
    db: Database    # ✓ Database is @service-decorated (CF_SERVICE_MARKER) — injected
    retries: int    # ✗ plain type — ignored

# resolve_deps(Auth) → {"db": Database}
```

### `resolve_deps(cls)` { #resolve-deps }

`resolve_deps` (`engine/dependencies.py`) calls `get_type_hints(cls)` and keeps only annotations
whose type is a class carrying `CF_SERVICE_MARKER` (i.e. a `@service`/`@module`-decorated class). It
unwraps `Optional[T]` / `T | None` via `unwrap_optional` before the check. Plain-typed attributes
(`name: str`) are never injected.

### `topological_sort(registry)` { #topological-sort }

Uses Kahn's algorithm:

1. Build an adjacency list from `resolve_deps()` over all registered entries.
2. Compute the in-degree of every node.
3. Seed a queue with the in-degree-0 nodes.
4. Pop nodes, appending to the result and decrementing neighbours' in-degrees.
5. If the result doesn't cover every node, a cycle exists → `CircularDependencyError`.

Config is **not** injected via DI. The parent module instantiates `config_cls` in `__init__` and
propagates the instance to children through `.config` during `init()`.

## Metadata & markers { #metadata }

Decorators attach metadata markers to classes; these drive all framework behavior. The complete set
of markers lives in `common/types.py`.

### Markers { #markers }

| Constant             | Value                   | Purpose |
|----------------------|-------------------------|---------|
| `CF_SERVICE_MARKER`  | `"__cf_service__"`      | Truthy on every `@service` and `@module` class. |
| `CF_SERVICE_META`    | `"__cf_service_meta__"` | Stores the `ServiceMeta` / `ModuleMeta` instance. |
| `CF_NAME_ATTR`       | `"__cf_name__"`         | The auto-generated component name. |

Hook markers (`__cf_before_startup__`, `__cf_before_shutdown__`) are set on methods by
`@before_startup` / `@before_shutdown` and mapped in `CF_HOOK_MARKER_MAP`.

### Meta types { #meta-types }

- **`ServiceMeta(name, config_cls=None)`** — set by `@service`.
- **`ModuleMeta(name, services, config_cls=None)`** — set by `@module`; extends `ServiceMeta` with
  the direct child `services` list.

### Type checks { #type-checks }

```python
def is_cf_service(cls):  # bool(getattr(cls, CF_SERVICE_MARKER, False))
def is_cf_module(cls):   # isinstance(getattr(cls, CF_SERVICE_META, None), ModuleMeta)
```

`is_cf_module` distinguishes a module from a plain service by the *type* of the stored meta:
`ModuleMeta` is a subclass of `ServiceMeta`, so a module satisfies both checks, while a plain
service satisfies only `is_cf_service`.

## Error hierarchy { #errors }

All framework errors inherit from `CanaryFrameworkError`, so callers can catch a single type to
handle any framework error (`common/errors.py`):

```
Exception
└── CanaryFrameworkError
    ├── ConfigurationError          # config load / validation failure
    ├── ServiceNotFoundError        # service/module lookup failure
    ├── CircularDependencyError     # topological sort detected a cycle
    ├── DependencyInjectionError    # DI wiring failure (e.g. a None instance)
    └── LifecycleHookError          # a lifecycle hook raised an unhandled exception
```
