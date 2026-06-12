# AGENTS.md — Canary Framework

## Quick commands

```bash
uv sync --extra dev --extra web          # install dev + web dependencies
uv run ruff check src/ tests/            # lint
uv run ruff format src/ tests/           # format
uv run mypy src/ tests/                  # type-check (strict)
uv run pytest                            # run all tests (asyncio_mode=auto)
uv run pytest tests/unit/test_foo.py     # run a single test file
uv run pytest -m unit                    # run only unit tests
uv run pytest -m "not slow"              # skip slow tests
uv run pytest --cov=src/canary_framework --cov-fail-under=70
```

## Pre-commit

```bash
uv run pre-commit run --all-files
```

Hooks: ruff (lint+format), mypy strict on `src/`, plus trailing-whitespace/EOF/etc.

## Version must match in 3 places

When bumping version:
1. `pyproject.toml` → `project.version`
2. `src/canary_framework/__init__.py` → `__version__`
3. Release branch name → `releases/v<version>`

The publish workflow validates all three match before building.

## Code style

- Line length: 100 (ruff)
- Double quotes (ruff format)
- Python 3.12+ syntax (no `from __future__ import annotations` needed, but it's used)
- Docstrings/comments: bilingual Chinese + English

## Architecture notes

- **Single package**: `src/canary_framework/` (hatchling wheel build, `src/` layout)
- **Layer order**: `common/` (zero internal deps) → `engine/` → `core/` → `decorators/`
- **ModuleBase extends ServiceBase** — modules are composable services; the tree root is always a module
- **DI mechanism**: type annotations on classes. `resolve_deps()` reads `get_type_hints()`, filters by `__cf_service__` marker. Kahn's algorithm produces topological start order.
- **Registry**: write-once during `configure()`, then read-only. Parent-child chaining for nested modules.
- **Dependencies**: pydantic + starlette (core). uvicorn is an optional `[web]` extra, not a core dependency.
- **`py.typed`** marker present — PEP 561 compliant package

## Testing

- `tests/unit/` — isolated, no framework engine
- `tests/integration/` — multi-component wiring
- `tests/functional/` — end-to-end with ASGI
- Markers: `unit`, `integration`, `functional`, `slow`
- asyncio_mode = `auto` in pytest config — no `@pytest.mark.asyncio` needed

## Common/test conventions

- Test side-effect: `uv sync --extra dev --extra web` pulls in web deps even for unit tests (httpx is needed by some tests)
- `__init__.py` is the public API surface — all public exports flow through it

## Commit messages

```
类型: 简短描述
```
Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
