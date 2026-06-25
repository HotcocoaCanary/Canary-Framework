"""Parameter resolution engine for Canary Framework."""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import iscoroutinefunction
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from starlette.requests import Request
from starlette.responses import Response


def resolve_params(route_fn: Any) -> dict[str, tuple[Any, bool, Any]]:
    """解析路由处理器函数的参数注解、默认值和默认对象。

    返回 {param_name: (annotation, has_default, default_value)}，
    "self" 参数被跳过。
    """
    sig = inspect.signature(route_fn)
    try:
        type_hints = inspect.get_annotations(route_fn)
    except Exception as e:
        warnings.warn(
            f"Failed to resolve annotations for '{getattr(route_fn, '__name__', route_fn)}': {e}",
            stacklevel=2,
        )
        type_hints = {}

    result: dict[str, tuple[Any, bool, Any]] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        annotation = type_hints.get(
            name,
            param.annotation if param.annotation is not inspect.Parameter.empty else str,
        )
        has_default = param.default is not inspect.Parameter.empty
        default_value = param.default if has_default else None
        result[name] = (annotation, has_default, default_value)
    return result


@dataclass(slots=True)
class EndpointMeta:
    """Metadata representing a fully resolved endpoint's parameters and expected body."""

    call: Callable[..., Any]
    path_params: dict[str, tuple[type | None, bool, FieldInfo | None]] = field(default_factory=dict)
    query_params: dict[str, tuple[type | None, bool, FieldInfo | None]] = field(
        default_factory=dict
    )
    body_model: type[BaseModel] | None = None
    body_param_name: str | None = None
    request_param_name: str | None = None
    response_param_name: str | None = None
    use_cache: bool = True
    is_coroutine: bool = False

    @property
    def param_types(self) -> dict[str, type | None]:
        """Aggregate all parameter types for fast lookup."""
        types: dict[str, type | None] = {}
        for name, meta in self.path_params.items():
            types[name] = meta[0]
        for name, meta in self.query_params.items():
            types[name] = meta[0]
        return types


def resolve_endpoint_meta(
    *,
    path: str,
    call: Callable[..., Any],
    is_endpoint: bool = False,
    request_model: type[BaseModel] | None = None,
    http_method: str = "GET",
) -> EndpointMeta:
    """Resolve endpoint parameters into an EndpointMeta node.

    Args:
        path: The route path (e.g., "/users/{user_id}").
        call: The endpoint function.
        is_endpoint: Whether the callable is an actual endpoint (vs a sub-dependency).
        request_model: Explicit body model from RouteDef.
        http_method: HTTP method, helps infer body if not provided.

    Returns:
        An EndpointMeta node representing the endpoint parameter structure.
    """
    from starlette.routing import compile_path

    _, _, path_regex_dict = compile_path(path)
    path_param_names = set(path_regex_dict.keys())

    endpoint_meta = EndpointMeta(
        call=call,
        is_coroutine=iscoroutinefunction(call),
    )

    params = resolve_params(call)

    # Resolve parameters
    for name, (ann, has_default, default_value) in params.items():
        import types
        from typing import Union

        ann_origin = getattr(ann, "__origin__", None)
        ann_args = getattr(ann, "__args__", ())
        is_union = ann_origin is Union or type(ann) is types.UnionType
        is_request = ann is Request or (is_union and Request in ann_args)
        is_response = ann is Response or (is_union and Response in ann_args)

        if is_request:
            endpoint_meta.request_param_name = name
            continue
        if is_response:
            endpoint_meta.response_param_name = name
            continue

        # Body model detection (endpoints only for now)
        if is_endpoint and request_model is not None and ann is request_model:
            endpoint_meta.body_model = request_model
            endpoint_meta.body_param_name = name
            continue

        if (
            is_endpoint
            and request_model is None
            and http_method not in ("GET", "DELETE")
            and isinstance(ann, type)
            and issubclass(ann, BaseModel)
        ):
            endpoint_meta.body_model = ann
            endpoint_meta.body_param_name = name
            continue

        from pydantic.fields import FieldInfo

        field_info = default_value if isinstance(default_value, FieldInfo) else None
        if name in path_param_names:
            endpoint_meta.path_params[name] = (ann, has_default, field_info)
        else:
            # Query param
            endpoint_meta.query_params[name] = (ann, has_default, field_info)

    # Handle the case where a body model was provided explicitly in RouteDef
    # but the endpoint function doesn't take it as a named parameter.
    # We still need it for OpenAPI.
    if is_endpoint and endpoint_meta.body_model is None and request_model is not None:
        endpoint_meta.body_model = request_model

    return endpoint_meta


__all__ = ["EndpointMeta", "resolve_endpoint_meta"]
