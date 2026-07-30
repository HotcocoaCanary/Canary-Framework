# Routers and HTTP

Declare a Router by inheriting `RouterBase` and applying `@router`.

```python
from canary_framework import delete, get, patch, post, put, router
from canary_framework.core import RouterBase

@router(prefix="/items", tags=("Items",))
class ItemsRouter(RouterBase):
    @get("/{item_id}")
    async def read(self, item_id: int) -> dict[str, int]:
        return {"id": item_id}
```

## Paths and parameters

- Path template: `/{item_id}` binds `item_id`.
- Query template: `/search?q={query}&page={page}` binds query keys to named parameters.
- Defaults, `T | None`, Pydantic `Field` metadata, scalar conversion, and boolean forms are supported.
- Missing or invalid request values return 422.

## Bodies and responses

Set `request_model` for a Pydantic request body and `response_model` for conversion/schema output. A handler may return a body, a Starlette `Response`, or `(body, status_code)`. The declared `status_code` is the default.

Endpoint options are `request_model`, `response_model`, `status_code`, `tags`, `summary`, `description`, `deprecated`, `operation_id`, and `responses`.

## OpenAPI and docs

The initialized runtime root compiles `/openapi.json`, `/docs`, and `/redoc` from all descendant routes. One root config owns metadata, security schemes, servers, and docs paths. Nested metadata contributes operation context but cannot replace root document metadata.

Duplicate routes, operation IDs, docs-path collisions, unknown security schemes, and incompatible schema names fail during initialization.
