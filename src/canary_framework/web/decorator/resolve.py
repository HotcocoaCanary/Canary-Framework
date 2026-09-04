"""Parameter resolution — turn a handler signature into (type, source, default).

参数求解：把 handler 的签名参数解析为「类型 + 来源标记 + 默认值」，供请求分发
（:mod:`canary_framework.web.core.routing`）与文档生成
（:mod:`canary_framework.web.core.openapi`）共用，避免两处漂移。
"""

from __future__ import annotations

import datetime
import decimal
import enum
import inspect
import pathlib
import re
import types
import uuid
from collections.abc import Callable
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from starlette.requests import Request

from canary_framework.web.decorator.params import _UNDEFINED, Param

_EMPTY = inspect.Parameter.empty
_PATH_PARAM = re.compile(r"\{([A-Za-z_]\w*)")
_PATH_PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)(?::[^}]+)?\}")

# 能无歧义地从一个字符串还原出来的类型——URL 的查询串与路径段只装得下字符串，
# 所以「是不是标量」就是「能不能走 query / path」的判据，不是一份特例清单。
_SCALARS = (
    str,
    bytes,
    bool,
    int,
    float,
    complex,
    uuid.UUID,
    decimal.Decimal,
    datetime.date,
    datetime.datetime,
    datetime.time,
    datetime.timedelta,
    pathlib.PurePath,
)


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


def is_scalar(type_: Any) -> bool:
    """Whether *type_* can be reconstructed from a single string (recursively).

    标量判定：容器与联合按元素递归；未注解 / ``Any`` 视为标量（保持旧行为）。
    """
    if type_ is _EMPTY or type_ is Any or type_ is None or type_ is type(None):
        return True
    origin = get_origin(type_)
    if origin is Literal:
        return True
    if origin in (Union, types.UnionType):
        return all(is_scalar(arg) for arg in get_args(type_))
    if origin in (list, set, frozenset, tuple):
        args = [a for a in get_args(type_) if a is not Ellipsis]
        return bool(args) and all(is_scalar(a) for a in args)
    if inspect.isclass(type_):
        return issubclass(type_, enum.Enum) or issubclass(type_, _SCALARS)
    return False


def location_of(type_: Any, marker: Param | None, name: str, path_params: set[str]) -> str:
    """Decide a parameter's source. Explicit marker wins; otherwise infer.

    推断规则一句话：**标量走 query（名字命中路径占位符则走 path），其余走 body。**
    模型、``dict``、``list[Model]`` 都属于「其余」，不再被误当成查询参数。
    """
    if marker is not None:
        return marker.location
    if type_ is Request:
        return "request"
    if name in path_params:
        return "path"
    return "query" if is_scalar(type_) else "body"


def path_param_names(path: str) -> set[str]:
    """Extract ``{name}`` placeholders (ignoring an optional ``:converter``)."""
    return {m.group(1) for m in _PATH_PARAM.finditer(path)}


def documented_path(path: str) -> str:
    """Strip Starlette's ``:converter`` suffixes — OpenAPI only knows ``{name}``.

    ``/files/{name:path}`` → ``/files/{name}``。转换器是 Starlette 的路由语法，
    不是 OpenAPI 的；泄漏进文档会让 Swagger UI 把它当成参数名的一部分。
    """
    return _PATH_PLACEHOLDER.sub(r"{\1}", path)
