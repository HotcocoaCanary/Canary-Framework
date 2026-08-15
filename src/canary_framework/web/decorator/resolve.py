"""Parameter resolution — turn a handler signature into (type, source, default).

参数求解：把 handler 的签名参数解析为「类型 + 来源标记 + 默认值」，供请求分发
（:mod:`canary_framework.web.core.routing`）与文档生成
（:mod:`canary_framework.web.core.openapi`）共用，避免两处漂移。
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel
from starlette.requests import Request

from canary_framework.web.decorator.params import _UNDEFINED, Param

_EMPTY = inspect.Parameter.empty
_PATH_PARAM = re.compile(r"\{([A-Za-z_]\w*)")


def hints_of(fn: Callable[..., object]) -> dict[str, Any]:
    """Resolve the handler's type hints (including ``Annotated`` extras).

    解析 handler 的类型注解；用 ``__func__`` 取底层函数，保证 ``__globals__`` 可靠。
    """
    return get_type_hints(getattr(fn, "__func__", fn), include_extras=True)


def unwrap(annotation: Any) -> tuple[Any, Param | None]:
    """Split ``Annotated[T, Param(...)]`` into ``(T, marker)``; pass others through."""
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        for meta in args[1:]:
            if isinstance(meta, Param):
                return args[0], meta
        return args[0], None
    return annotation, None


def resolve_meta(annotation: Any, param_default: Any) -> tuple[Any, Param | None, Any]:
    """Return ``(type, marker, default)``; ``default`` is :data:`_EMPTY` when required.

    兼容两种写法：
    - ``Annotated[int, Query(...)]``（标记在注解里）；
    - ``int = Query(...)``（标记作为默认值，FastAPI 经典写法）。
    """
    type_, marker = unwrap(annotation)
    if marker is not None:
        default = marker.default if marker.default is not _UNDEFINED else param_default
        return type_, marker, default
    if isinstance(param_default, Param):
        marker = param_default
        default = marker.default if marker.default is not _UNDEFINED else _EMPTY
        return type_, marker, default
    return type_, None, param_default


def location_of(type_: Any, marker: Param | None, name: str, path_params: set[str]) -> str:
    """Decide a parameter's source. Explicit marker wins; otherwise infer."""
    if marker is not None:
        return marker.location
    if type_ is Request:
        return "request"
    if inspect.isclass(type_) and issubclass(type_, BaseModel):
        return "body"
    if name in path_params:
        return "path"
    return "query"


def path_param_names(path: str) -> set[str]:
    """Extract ``{name}`` placeholders (ignoring an optional ``:converter``)."""
    return {m.group(1) for m in _PATH_PARAM.finditer(path)}
