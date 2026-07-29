"""Router and endpoint declaration decorators."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Protocol

from canary_framework.common import (
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    CanaryConfig,
    ResponseSpec,
    RouterMeta,
    RouteSpec,
)
from canary_framework.core.router import RouterBase

_ROUTE_SPECS_ATTR = "__cf_route_specs__"
_HANDLER_ROUTE_SPECS_ATTR = "__cf_handler_route_specs__"


def _route[**P, R](
    method: str,
    path: str,
    *,
    request_model: type | None = None,
    response_model: type | None = None,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: Mapping[int | str, ResponseSpec] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Attach one immutable route specification without wrapping the handler."""

    def decorate(handler: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        spec = RouteSpec(
            method=method,
            local_path=path,
            handler_name=handler.__name__,
            request_model=request_model,
            response_model=response_model,
            status_code=status_code,
            tags=tuple(tags),
            summary=summary,
            description=description,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses or {},
        )
        current = tuple(getattr(handler, _HANDLER_ROUTE_SPECS_ATTR, ()))
        setattr(handler, _HANDLER_ROUTE_SPECS_ATTR, (*current, spec))
        return handler

    return decorate


class _RouteDecorator(Protocol):
    """Typed public endpoint decorator factory."""

    def __call__[**P, R](
        self,
        path: str,
        *,
        request_model: type | None = None,
        response_model: type | None = None,
        status_code: int = 200,
        tags: Sequence[str] = (),
        summary: str | None = None,
        description: str | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: Mapping[int | str, ResponseSpec] | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        """Declare a route and preserve the decorated handler's type."""
        raise NotImplementedError


def _method_decorator(method: str, public_name: str) -> _RouteDecorator:
    """Create one named, typed HTTP method decorator."""

    def declare[**P, R](
        path: str,
        *,
        request_model: type | None = None,
        response_model: type | None = None,
        status_code: int = 200,
        tags: Sequence[str] = (),
        summary: str | None = None,
        description: str | None = None,
        deprecated: bool = False,
        operation_id: str | None = None,
        responses: Mapping[int | str, ResponseSpec] | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        return _route(
            method,
            path,
            request_model=request_model,
            response_model=response_model,
            status_code=status_code,
            tags=tags,
            summary=summary,
            description=description,
            deprecated=deprecated,
            operation_id=operation_id,
            responses=responses,
        )

    declare.__name__ = public_name
    return declare


get = _method_decorator("GET", "get")
post = _method_decorator("POST", "post")
put = _method_decorator("PUT", "put")
delete = _method_decorator("DELETE", "delete")
patch = _method_decorator("PATCH", "patch")


def router(
    *,
    prefix: str = "",
    tags: Sequence[str] = (),
    security: Sequence[str] = (),
    config: type[CanaryConfig] | None = None,
) -> Callable[[type[RouterBase]], type[RouterBase]]:
    """Declare a router node and collect its local endpoint specifications."""
    if config is not None and not issubclass(config, CanaryConfig):
        raise TypeError("router config must inherit from CanaryConfig.")

    def decorate(cls: type[RouterBase]) -> type[RouterBase]:
        if not issubclass(cls, RouterBase):
            raise TypeError(f"@router '{cls.__name__}' must inherit from RouterBase.")
        specs = tuple(
            spec
            for value in cls.__dict__.values()
            for spec in getattr(value, _HANDLER_ROUTE_SPECS_ATTR, ())
        )
        meta = RouterMeta(
            name=cls.__name__,
            prefix=prefix,
            tags=tuple(tags),
            security=tuple(security),
            config_cls=config,
        )
        setattr(cls, _ROUTE_SPECS_ATTR, specs)
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, meta)
        setattr(cls, CF_NAME_ATTR, cls.__name__)
        return cls

    return decorate


__all__ = ["delete", "get", "patch", "post", "put", "router"]
