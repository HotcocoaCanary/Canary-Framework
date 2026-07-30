"""Immutable route parameter analysis shared by route compilers."""

from __future__ import annotations

import inspect
import re
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, get_type_hints

from pydantic.fields import FieldInfo

from canary_framework.common.routing import ResolvedRoute

_PARAM_PATTERN = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    annotation: Any
    has_default: bool
    default: object
    field_info: FieldInfo | None


@dataclass(frozen=True, slots=True)
class RouteAnalysis:
    starlette_path: str
    path_params: tuple[str, ...]
    query_params: tuple[str, ...]
    parameters: Mapping[str, ParameterSpec]
    request_model: type | None
    body_param: str | None


def _normalize_path(path: str) -> str:
    normalized = "/" + "/".join(part for part in path.split("/") if part)
    return "/" if normalized == "/" else normalized


def _handler_parameters(handler: Any) -> dict[str, ParameterSpec]:
    signature = inspect.signature(handler)
    try:
        hints = get_type_hints(handler, include_extras=True)
    except Exception as exc:
        warnings.warn(
            f"Failed to resolve annotations for '{getattr(handler, '__name__', handler)}': {exc}",
            stacklevel=3,
        )
        hints = {}

    parameters: dict[str, ParameterSpec] = {}
    for name, parameter in signature.parameters.items():
        if name == "self":
            continue
        annotation = hints.get(
            name,
            parameter.annotation if parameter.annotation is not inspect.Parameter.empty else str,
        )
        default = parameter.default
        parameters[name] = ParameterSpec(
            annotation=annotation,
            has_default=default is not inspect.Parameter.empty,
            default=None if default is inspect.Parameter.empty else default,
            field_info=default if isinstance(default, FieldInfo) else None,
        )
    return parameters


def analyze_route(route: ResolvedRoute) -> RouteAnalysis:
    local_path, separator, query_template = route.full_path.partition("?")
    path_params = tuple(_PARAM_PATTERN.findall(local_path))
    query_params = tuple(_PARAM_PATTERN.findall(query_template)) if separator else ()
    parameters = _handler_parameters(route.handler)
    templated = set(path_params) | set(query_params)
    body_candidates = tuple(name for name in parameters if name not in templated)
    body_param = (
        body_candidates[0]
        if route.spec.request_model is not None and len(body_candidates) == 1
        else None
    )
    return RouteAnalysis(
        starlette_path=_normalize_path(local_path),
        path_params=path_params,
        query_params=query_params,
        parameters=MappingProxyType(parameters),
        request_model=route.spec.request_model,
        body_param=body_param,
    )


__all__ = ["ParameterSpec", "RouteAnalysis", "analyze_route"]
