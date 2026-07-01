# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Canary Framework is a lightweight, decorator-driven async service framework for Python 3.12+, built on Starlette + Pydantic. Core philosophy: **services are the smallest unit, modules compose services, and a module *is* a service** (`ModuleBase` extends `ServiceBase`).

## Commands

`AGENTS.md` is the source of truth for commands, code style, and release steps — read it. The essentials:

```bash
uv sync --extra dev --extra web              # install (web extra is needed even for unit tests — httpx)
uv run ruff check src/ tests/                # lint
uv run ruff format src/ tests/               # format
uv run mypy src/ tests/                      # strict type-check
uv run pytest                                # all tests (asyncio_mode=auto — no @pytest.mark.asyncio)
uv run pytest tests/unit/test_router.py      # single file
uv run pytest tests/unit/test_router.py::test_name   # single test
uv run pytest -m unit                        # by marker: unit | integration | functional | slow
uv run pre-commit run --all-files            # ruff + mypy(strict on src/) + hygiene hooks
```

Version must be bumped in three places in sync (`pyproject.toml`, `__init__.py:__version__`, release branch `releases/v<version>`) — the publish workflow validates this. See AGENTS.md.

## Architecture

The package (`src/canary_framework/`) is strictly layered; imports only flow downward:

```
common/      zero internal deps — types, markers, config, errors, logging
  ↓
engine/      registry, dependency resolution + topo sort, openapi, params
  ↓
core/        ServiceBase, ModuleBase, Router (the base classes users subclass)
  ↓
decorators/  @service, @module, @config, @before_startup, @before_shutdown
```

`__init__.py` is the entire public API surface — every public symbol is re-exported there. When adding a public name, wire it through `__init__.py`'s imports **and** `__all__`.

### How DI works (the central mechanism)

Dependencies are declared as **bare class-level type annotations**, not constructor args:

```python
@service()
class UserService(ServiceBase):
    db: Database          # ← this annotation IS the dependency declaration
```

The flow, spread across several files:

1. **Marking** — `@service`/`@module` set `__cf_service__` / `__cf_service_meta__` markers on the class (see `common/types.py` for all marker constants and `is_cf_service`/`is_cf_module` helpers).
2. **Resolution** — `engine/dependencies.py::resolve_deps()` calls `get_type_hints()` and keeps only annotations whose type carries `CF_SERVICE_MARKER`. It unwraps `Optional[T]` / `T | None`. **A type annotation is only injected if its class is `@service`/`@module`-decorated** — plain-typed attributes (`name: str`) are ignored.
3. **Registration** — `ModuleBase.init()` recursively registers each declared service *and its transitive dependencies* into a `Registry` (`engine/registry.py`). The registry is write-once during init, then read-only; it has parent→child chaining so nested modules resolve up the tree.
4. **Ordering** — `topological_sort()` (Kahn's algorithm) produces start order; a cycle raises `CircularDependencyError`.
5. **Wiring** — `ModuleBase._wire_service()` does `setattr(instance, attr_name, dep_instance)` using the annotation's attribute name. Instantiation, wiring, and `init()` all happen in topological order.

### Lifecycle

Three phases, all driven by `ModuleBase` over its children:

- `init()` — **synchronous**. Registers, sorts, instantiates, wires, then calls each child's `init()` in topo order. Config is instantiated earlier (in `__init__`) so `log_level` applies before anything else runs.
- `startup()` — **async**. Fires `@before_startup` hooks, runs each child's `startup()` in topo order.
- `shutdown()` — **async**. Fires `@before_shutdown` hooks, runs children in **reverse** topo order.

`@before_startup`/`@before_shutdown` mark methods via `CF_HOOK_MARKER_MAP`; `core/service/_hooks.py::find_hooks()` discovers them and `_invoke_hook()` wraps failures in `LifecycleHookError`.

### ASGI / routing

`ServiceBase` is itself an ASGI app (`__call__` handles the lifespan protocol → `startup`/`shutdown`, everything else → `asgi_app`). A `Router` is declared as a class attribute (`router = Router(prefix=..., tags=...)`) and routes via `@router.get(...)` decorators; each route's metadata is captured as a `RouteInfo` (`common/types.py`) with path/query/body params pre-parsed.

- `asgi_app` is built lazily and differs by context: standalone (no parent registry) includes the router prefix and doc endpoints; mounted-in-a-module it does not (the parent owns prefixing and doc aggregation).
- **OpenAPI is generated only at the top level** — `_cf_generate_openapi()` runs when `_cf_parent_registry is None`, collecting `RouteInfo`s across the whole tree via `_cf_collect_route_infos()` and building `/openapi.json`, `/docs`, `/redoc` (`engine/openapi.py`). Root-level routes (the doc endpoints) propagate up from nested modules via `_cf_get_root_routes()`.

Standard entry point: `app = App(); await app.init()` then `uvicorn.run(app, lifespan="on")`.

## Conventions

- Docstrings and comments are **bilingual (Chinese + English)** throughout — match this when editing.
- Commit messages: `类型: 简短描述` with types `feat|fix|docs|refactor|test|chore`.
- `uvicorn` is an optional `[web]` extra, not a core dependency — don't import it in `src/`.
- Runnable, tested usage examples live in `examples/01_*.py` … `10_full_app.py`; consult them for the intended public-API patterns.
