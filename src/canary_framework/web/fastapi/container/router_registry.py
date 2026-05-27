"""Route registration — bind ``@router``-decorated services to a FastAPI app.

Consumes :meth:`Registry.entries_with_meta` to discover ``RouterMeta``
entries, then builds FastAPI native ``APIRouter`` instances and registers
their HTTP endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from canary_framework.common._types import RouterMeta
from canary_framework.core.container.registry import Registry
from canary_framework.web.fastapi.decorators.router import get_route_info


def register_routes(app: FastAPI, registry: Registry) -> None:
    """Register all ``@router``-decorated services on a FastAPI app.

    For each router entry:
    1. Build an ``APIRouter`` with the group prefix and tags.
    2. For each route method (pre-scanned and stored in ``RouterMeta.routes``
       at decoration time), bind it to the service instance and register
       with FastAPI.
    3. Include the router.
    """
    from fastapi import APIRouter

    for entry, meta in registry.entries_with_meta(RouterMeta):
        api_router = APIRouter(prefix=meta.prefix, tags=meta.tags)  # type: ignore[arg-type]

        for method in meta.routes:
            http_method, path, kwargs = get_route_info(method)
            bound = getattr(entry.instance, method.__name__)
            api_router.add_api_route(
                path=path,
                endpoint=bound,
                methods=[http_method],
                **kwargs,
            )

        app.include_router(api_router)
