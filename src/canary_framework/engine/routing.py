"""Pure route-context extension and router route resolution helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import cast

from canary_framework.common.routing import ResolvedRoute, RouteContext, _RouteOwner
from canary_framework.common.types import RouterMeta


def normalize_path(path: str) -> str:
    base, separator, query = path.partition("?")
    normalized = "/" + "/".join(part for part in base.split("/") if part)
    if separator:
        return f"{normalized}?{query}"
    return "/" if normalized == "/" else normalized


def join_paths(*parts: str) -> str:
    path, separator, query = "/".join(parts).partition("?")
    normalized = normalize_path(path)
    return f"{normalized}?{query}" if separator else normalized


def ordered_unique(*groups: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for group in groups for value in group))


def extend_context(
    context: RouteContext,
    *,
    prefix: str,
    tags: tuple[str, ...],
    security: tuple[str, ...],
) -> RouteContext:
    return RouteContext(
        prefix=join_paths(context.prefix, prefix) if prefix or context.prefix else "",
        tags=ordered_unique(context.tags, tags),
        security=ordered_unique(context.security, security),
    )


def resolve_router_routes(
    owner: _RouteOwner,
    meta: RouterMeta,
    context: RouteContext,
) -> tuple[ResolvedRoute, ...]:
    effective = extend_context(
        context,
        prefix=meta.prefix,
        tags=meta.tags,
        security=meta.security,
    )
    routes: list[ResolvedRoute] = []
    for spec in owner.route_specs:
        bound = cast("Callable[..., Awaitable[object]]", getattr(owner, spec.handler_name))
        routes.append(
            ResolvedRoute(
                owner=owner,
                method=spec.method,
                full_path=join_paths(effective.prefix, spec.local_path),
                handler=bound,
                spec=spec,
                tags=ordered_unique(effective.tags, spec.tags),
                security=effective.security,
            )
        )
    return tuple(routes)


__all__ = [
    "extend_context",
    "join_paths",
    "normalize_path",
    "ordered_unique",
    "resolve_router_routes",
]
