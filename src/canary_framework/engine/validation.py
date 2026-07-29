"""Deterministic route validation before ASGI or OpenAPI compilation."""

from __future__ import annotations

from dataclasses import dataclass

from canary_framework.common.config import CanaryConfig
from canary_framework.common.errors import RouteCompilationError
from canary_framework.common.routing import ResolvedRoute
from canary_framework.engine.params import RouteAnalysis, analyze_route


def _normalize_path(path: str) -> str:
    """Normalize a configured or resolved path without changing root."""
    base = path.partition("?")[0]
    normalized = "/" + "/".join(part for part in base.split("/") if part)
    return "/" if normalized == "/" else normalized


def _context(route: ResolvedRoute) -> str:
    return f"{type(route.owner).__name__} {route.method} {route.full_path}"


def _error(route: ResolvedRoute, message: str) -> RouteCompilationError:
    return RouteCompilationError(f"{_context(route)}: {message}")


@dataclass(frozen=True, slots=True)
class ValidatedRoute:
    """A route paired with its canonical analysis and effective operation ID."""

    route: ResolvedRoute
    analysis: RouteAnalysis
    operation_id: str


def validate_routes(
    routes: tuple[ResolvedRoute, ...], config: CanaryConfig
) -> tuple[ValidatedRoute, ...]:
    """Analyze and validate all routes in deterministic declaration order."""
    analyses = tuple((route, analyze_route(route)) for route in routes)

    seen_paths: dict[tuple[str, str], ResolvedRoute] = {}
    for route, analysis in analyses:
        key = (route.method.upper(), analysis.starlette_path)
        if key in seen_paths:
            raise _error(route, f"duplicate route {route.method.upper()} {analysis.starlette_path}")
        seen_paths[key] = route

    seen_operation_ids: dict[str, ResolvedRoute] = {}
    for route, _analysis in analyses:
        operation_id = route.operation_id
        if operation_id in seen_operation_ids:
            raise _error(route, f"duplicate operationId {operation_id}")
        seen_operation_ids[operation_id] = route

    docs_paths = {
        _normalize_path(config.docs_openapi_path),
        _normalize_path(config.docs_swagger_path),
        _normalize_path(config.docs_redoc_path),
    }
    for route, analysis in analyses:
        if analysis.starlette_path in docs_paths:
            raise _error(
                route,
                f"business route {route.method.upper()} {analysis.starlette_path} "
                "conflicts with documentation endpoint",
            )

    validated: list[ValidatedRoute] = []
    security_schemes = config.openapi_security_schemes
    for route, analysis in analyses:
        for name in analysis.path_params:
            if name not in analysis.parameters:
                raise _error(route, f"path parameter {name} has no handler parameter")
        for name in analysis.query_params:
            if name not in analysis.parameters:
                raise _error(route, f"query parameter {name} has no handler parameter")

        templated = set(analysis.path_params) | set(analysis.query_params)
        body_candidates = tuple(name for name in analysis.parameters if name not in templated)
        if analysis.request_model is not None:
            if len(body_candidates) > 1:
                raise _error(route, "multiple request body declarations")
            if len(body_candidates) != 1:
                raise _error(route, "request model requires exactly one body parameter")
        elif body_candidates:
            raise _error(route, f"body parameter {body_candidates[0]} requires request model")

        for name in route.security:
            if name not in security_schemes:
                raise _error(route, f"unknown security scheme {name}")

        validated.append(
            ValidatedRoute(route=route, analysis=analysis, operation_id=route.operation_id)
        )
    return tuple(validated)


__all__ = ["ValidatedRoute", "validate_routes"]
