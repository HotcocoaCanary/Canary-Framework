# API Reference

## Public declarations

### `service`

```text
service() -> Callable[[type[ServiceBase]], type[ServiceBase]]
```

`service` takes no parameters. It validates and marks a `ServiceBase` subclass as a lifecycle and dependency-injection node. The returned value is the same class, not a wrapper. See [Services](services.md).

### `config`

```text
config() -> Callable[[type[CanaryConfig]], type[CanaryConfig]]
```

`config` takes no parameters. The returned class decorator requires a `CanaryConfig` subclass, marks it as a framework configuration class, and returns the same class without wrapping or instantiating it. Applying it to any other class raises `TypeError`. Router and Module `config=` arguments also require a `CanaryConfig` subclass. See [Configuration](configuration.md) for every built-in field.

### `router`

```text
router(*, prefix: str = "", tags: Sequence[str] = (),
       security: Sequence[str] = (),
       config: type[CanaryConfig] | None = None)
    -> Callable[[type[RouterBase]], type[RouterBase]]
```

- `prefix`: path prefix prepended to every endpoint owned by the Router.
- `tags`: tags inherited by all Router endpoints, after ancestor Module tags.
- `security`: OpenAPI security scheme names appended to inherited names with ordered de-duplication. Each name must exist in the runtime root config.
- `config`: configuration class used only when this Router is the runtime root. A Router composed under a Module receives the Module-selected config.
- Return: a class decorator that validates and returns the same `RouterBase` subclass with its endpoint metadata attached.

See [Web and routing](web.md) and [Configuration](configuration.md).

### `module`

```text
module(*, children: Sequence[type] = (), prefix: str = "",
       tags: Sequence[str] = (), security: Sequence[str] = (),
       config: type[CanaryConfig] | None = None)
    -> Callable[[type[ModuleBase]], type[ModuleBase]]
```

- `children`: explicitly composed decorated Service, Router, or Module classes, kept in declaration order. Config classes are not children.
- `prefix`: path prefix prepended recursively to Router descendants.
- `tags`: tags prepended to descendant endpoint tags.
- `security`: security scheme names inherited by descendants with ordered de-duplication.
- `config`: configuration class selected for this Module scope. Without one, a nested Module inherits the nearest ancestor Module config; a root Module falls back to `CanaryConfig`.
- Return: a class decorator that validates and returns the same `ModuleBase` subclass as a DI scope and possible runtime root.

Modules cannot declare endpoints directly. See [Modules](modules.md).

## Endpoint decorators

`get`, `post`, `put`, `delete`, and `patch` share this signature:

```text
(path: str, *, request_model: type | None = None,
 response_model: type | None = None, status_code: int = 200,
 tags: Sequence[str] = (), summary: str | None = None,
 description: str | None = None, deprecated: bool = False,
 operation_id: str | None = None,
 responses: Mapping[int | str, ResponseSpec] | None = None)
    -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]
```

- `path`: local endpoint path. Path templates such as `/{item_id}` bind path parameters. A query template such as `/search?q={query}&page={page}` declares and binds query parameters while the compiled Starlette path remains `/search`.
- `request_model`: request-body model. It selects the sole handler parameter not named by the path or query template.
- `response_model`: response model used only for OpenAPI schema generation and documentation; the actual body is serialized from the handler's return value.
- `status_code`: declared success status, default `200`.
- `tags`: endpoint-local tags appended after inherited Module and Router tags.
- `summary`: optional OpenAPI operation summary.
- `description`: optional OpenAPI operation description.
- `deprecated`: emits the OpenAPI `deprecated: true` marker when enabled.
- `operation_id`: explicit OpenAPI operation ID. By default it is `RouterClass.handler_name`; duplicates fail route compilation.
- `responses`: additional or overriding response documentation keyed by integer or string status. Each value is `ResponseSpec(description, model)`.
- Return: a decorator that records immutable route metadata and returns the original typed async handler without wrapping it.

Status precedence is explicit: a returned Starlette `Response` keeps its own status; `(body, integer_status)` uses the tuple status; otherwise `status_code` is used. `responses` documents statuses but does not change runtime status selection.

## Base classes

### `ServiceBase`

- `async init() -> None`: performs structural initialization, then `on_init()`.
- `async startup() -> None`: starts long-lived resources, then `on_startup()`.
- `async shutdown() -> None`: invokes `on_shutdown()` and stops resources.
- `config -> CanaryConfig | None`: config selected by the runtime root or containing Module.
- `lifecycle_state -> LifecycleState`: current lifecycle state.

The async extension points are `on_init()`, `on_startup()`, and `on_shutdown()`. `ServiceBase` is not ASGI and has no routing or OpenAPI API.

### `RouterBase` and `ModuleBase`

Both inherit the Service lifecycle. When used as the runtime root they additionally provide:

- `asgi_app`: the lazily compiled, cached ASGI application after initialization.
- `openapi() -> dict[str, object]`: the matching cached OpenAPI document.
- `async __call__(scope, receive, send) -> None`: ASGI HTTP and lifespan entry point.

`RouterBase.route_specs` exposes its immutable endpoint declarations. `ModuleBase.direct_children` exposes initialized direct children in declaration order. A Router or Module composed under another Module is not a runtime root and cannot serve or expose its own OpenAPI document.

## Lifecycle states and rollback

The states are `CREATED`, `INITIALIZED`, `STARTED`, `STOPPED`, and `FAILED`. The only legal public sequence is `await init()`, `await startup()`, then `await shutdown()`. Repeating a phase, skipping a phase, calling public `shutdown()` from `FAILED`, or using a stopped node again raises `LifecycleStateError`.

If initialization or startup fails, the node remains `FAILED`. The framework performs private, idempotent rollback of already initialized or started descendants in reverse lifecycle order and suppresses cleanup failures so they do not replace the original error. Rollback does not turn a failed node into `STOPPED` and is not a public lifecycle method. See [Lifecycle](lifecycle.md).

## Errors

Public errors include `ApplicationNotInitializedError`, `CircularDependencyError`, `ConfigurationError`, `DependencyDirectionError`, `DependencyInjectionError`, `LifecycleHookError`, `LifecycleStateError`, `RouteCompilationError`, and `ServiceNotFoundError`, all under `CanaryFrameworkError`.
