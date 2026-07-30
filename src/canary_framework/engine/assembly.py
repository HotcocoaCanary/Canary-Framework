"""Bundle validated routing, OpenAPI, and ASGI assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from starlette.routing import Router as StarletteRouter

from canary_framework.common.config import CanaryConfig
from canary_framework.common.routing import ASGIApp, ResolvedRoute
from canary_framework.engine.asgi import ASGICompiler
from canary_framework.engine.openapi import OpenAPICompiler
from canary_framework.engine.validation import validate_routes


@dataclass(frozen=True, slots=True)
class Assembly:
    routes: tuple[ResolvedRoute, ...]
    openapi: dict[str, object]
    asgi_app: ASGIApp


def compile_assembly(
    routes: tuple[ResolvedRoute, ...],
    *,
    config: CanaryConfig,
) -> Assembly:
    validated = validate_routes(routes, config=config)
    if not validated:
        return Assembly(
            routes=routes,
            openapi={},
            asgi_app=cast(ASGIApp, StarletteRouter(routes=[])),
        )

    openapi = OpenAPICompiler().compile(validated, config=config)
    asgi_app = ASGICompiler().compile(validated, openapi=openapi, config=config)
    return Assembly(routes=routes, openapi=openapi, asgi_app=asgi_app)


__all__ = ["Assembly", "compile_assembly"]
