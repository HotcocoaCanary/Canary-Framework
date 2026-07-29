"""Immutable routing declaration and resolution contracts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from starlette.types import Receive, Scope, Send

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class _RouteOwner(Protocol):
    """A node that owns route declarations."""

    @property
    def route_specs(self) -> tuple[RouteSpec, ...]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ResponseSpec:
    """Response documentation declaration."""

    description: str
    model: type | None = None


@dataclass(frozen=True, slots=True)
class RouteSpec:
    """Immutable node-local route declaration."""

    method: str
    local_path: str
    handler_name: str
    request_model: type | None = None
    response_model: type | None = None
    status_code: int = 200
    tags: tuple[str, ...] = ()
    summary: str | None = None
    description: str | None = None
    deprecated: bool = False
    operation_id: str | None = None
    responses: Mapping[int | str, ResponseSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", self.method.upper())
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "responses", MappingProxyType(dict(self.responses)))


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    """Immutable route with its context resolved."""

    owner: _RouteOwner
    method: str
    full_path: str
    handler: Callable[..., Awaitable[object]]
    spec: RouteSpec
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()

    @property
    def operation_id(self) -> str:
        return self.spec.operation_id or f"{type(self.owner).__name__}.{self.spec.handler_name}"


@dataclass(frozen=True, slots=True)
class RouteContext:
    """Inherited context used during route resolution."""

    prefix: str = ""
    tags: tuple[str, ...] = ()
    security: tuple[str, ...] = ()


__all__ = [
    "ASGIApp",
    "ResolvedRoute",
    "ResponseSpec",
    "RouteContext",
    "RouteSpec",
]
