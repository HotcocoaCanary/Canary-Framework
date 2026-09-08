"""Signature compilation — turn a handler signature into a fixed value-fetching plan.

签名编译：把 handler 的签名**在装配期**编译成一份固定的取值计划，请求到来时只是照着
计划取值，不再回头读签名。

为什么要编译。从前每处理一个请求都要重跑一遍 ``get_type_hints``（它会把字符串注解逐个
求值）、``inspect.signature``，还要为每个参数现造一个 ``TypeAdapter``——这三件都不便宜，
而它们的结果在类定义之后就再也不会变。现在这些只在启动时做一次，之后每个请求面对的是
一个扁平的元组。

同一份计划还供文档生成使用（:mod:`~canary_framework.web.core.openapi`）：**分发和文档
看的是同一个对象**，而不是各自遍历一遍签名再指望两边推断得一致——那种一致是约定，这种
一致是构造出来的。
"""

from __future__ import annotations

import datetime
import decimal
import enum
import inspect
import logging
import pathlib
import re
import types
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from pydantic import PydanticSchemaGenerationError, TypeAdapter
from starlette.requests import Request
from starlette.responses import Response

from canary_framework.web.decorator.params import Param
from canary_framework.web.infra.naming import header_name

_log = logging.getLogger("canary.web")

_EMPTY = inspect.Parameter.empty
_PATH_PARAM = re.compile(r"\{([A-Za-z_]\w*)")
_PATH_PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)(?::[^}]+)?\}")
_SKIPPED_KINDS = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)

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


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One handler parameter, fully resolved: where it comes from and how to validate it.

    一个形参的完整解法。装配期算好，请求期只读不算。

    :param name: Python 形参名，也是调用 handler 时的关键字。
    :param location: 取值来源——``path`` / ``query`` / ``header`` / ``cookie`` /
        ``body`` / ``request``（整个 :class:`~starlette.requests.Request` 对象）。
    :param source: 在来源里查找用的键。请求头已经转成协议名（``x_token`` → ``x-token``），
        其余情况就是形参名或 ``alias``。
    :param adapter: 校验/转换器。``None`` 表示原样透传——没有注解、注解是 ``Any``，
        或者这个类型 pydantic 根本描述不了。
    :param default: 缺省值；:data:`_EMPTY` 表示必填。
    :param multi: 是不是查询串里的多值参数（``list[...]``），决定用 ``getlist``。
    :param annotation: 原始类型注解，只供文档生成回看。
    :param description: ``Header(description=...)`` 之类的文档说明。
    """

    name: str
    location: str
    source: str
    adapter: TypeAdapter[Any] | None
    default: Any
    multi: bool
    annotation: Any
    description: str | None

    @property
    def required(self) -> bool:
        """没有缺省值就是必填。"""
        return self.default is _EMPTY


@dataclass(frozen=True, slots=True)
class HandlerPlan:
    """Everything the request path and the doc generator need to know about one handler.

    一个 handler 的全部解法：形参怎么取、返回值怎么序列化。

    :param params: 形参解法，按签名顺序。
    :param returns: 返回值的转换器；``None`` 表示直接交给 JSON 编码。
    :param returns_response: 返回注解本身就是 :class:`~starlette.responses.Response`
        的子类——媒体类型由 handler 自己决定，文档不该硬说成 JSON。
    :param response_annotation: 原始返回注解，供文档生成回看。
    """

    params: tuple[ParamSpec, ...]
    returns: TypeAdapter[Any] | None
    returns_response: bool
    response_annotation: Any


def build_plan(fn: Callable[..., object], path: str) -> HandlerPlan:
    """Compile *fn*'s signature against its route *path*, once, at assembly time.

    在装配期把 handler 的签名编译成 :class:`HandlerPlan`。``path`` 参与编译是因为
    「形参名是否命中路径占位符」决定了它走 path 还是 query。

    ``self`` / ``cls`` 与 ``*args`` / ``**kwargs`` 不参与绑定：前者是方法自身的接收者，
    后者没有名字可供从请求里查找。
    """
    hints = hints_of(fn)
    path_params = path_param_names(path)
    specs: list[ParamSpec] = []
    for name, param in inspect.signature(fn).parameters.items():
        if name in ("self", "cls") or param.kind in _SKIPPED_KINDS:
            continue
        type_, marker = unwrap(hints.get(name, param.annotation))
        location = location_of(type_, marker, name, path_params)
        alias = marker.alias if marker is not None and marker.alias else name
        specs.append(
            ParamSpec(
                name=name,
                location=location,
                source=header_name(alias) if location == "header" else alias,
                # Request 对象原样交出，不该也不能被校验。
                adapter=None if location == "request" else _adapter(type_, fn, name),
                default=param.default,
                multi=get_origin(type_) is list,
                annotation=type_,
                description=marker.description if marker is not None else None,
            )
        )

    returned = hints.get("return", _EMPTY)
    is_response = inspect.isclass(returned) and issubclass(returned, Response)
    return HandlerPlan(
        params=tuple(specs),
        returns=None if is_response else _adapter(returned, fn, "return"),
        returns_response=is_response,
        response_annotation=returned,
    )


def _adapter(annotation: Any, fn: Callable[..., object], where: str) -> TypeAdapter[Any] | None:
    """Build the validator for *annotation*, or ``None`` when there is nothing to validate.

    三种情况没有转换器：没写注解、注解是 ``Any``、注解是 ``None``——这些都表示"原样交给
    JSON 编码"。

    第四种是 pydantic 描述不了的类型（``TextIO``、``Callable``、自定义容器……）。它不该
    让整个应用起不来，也不该让整份文档 500——退化成"不校验、文档上不作约束"，并在**启动**
    时就记一条 WARNING 指名道姓。放在启动而不是第一次请求，是因为这种问题越早看见越好。
    """
    if annotation is _EMPTY or annotation is Any or annotation is type(None):
        return None
    try:
        return TypeAdapter(annotation)
    except (PydanticSchemaGenerationError, ValueError) as exc:
        _log.warning(
            "no schema for %r at %s.%s (%s); it will not be validated or documented",
            annotation,
            getattr(fn, "__qualname__", fn),
            where,
            type(exc).__name__,
        )
        return None


def hints_of(fn: Callable[..., object]) -> dict[str, Any]:
    """Resolve the handler's type hints (including ``Annotated`` extras).

    解析 handler 的类型注解；用 ``__func__`` 取底层函数，保证 ``__globals__`` 可靠。
    """
    return get_type_hints(getattr(fn, "__func__", fn), include_extras=True)


def unwrap(annotation: Any) -> tuple[Any, Param | None]:
    """Split ``Annotated[T, Header()]`` into ``(T, marker)``; pass others through.

    标记只能出现在 ``Annotated`` 里——把它写成默认值（FastAPI 的经典写法）会在装配期
    被 :func:`~canary_framework.web.infra.checks.require_annotated_sources` 拒绝，
    因为那让"默认值"这个位置同时表示两件事。
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        for meta in args[1:]:
            if isinstance(meta, Param):
                return args[0], meta
        return args[0], None
    return annotation, None


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
    模型、``dict``、``list[Model]`` 都属于「其余」，不会被误当成查询参数。

    只有请求头和 cookie 需要显式标记——它们在签名里不留任何痕迹，``x: str`` 看不出
    想读的是 ``X-Token`` 还是 ``?x=``。
    """
    if marker is not None:
        return marker.location
    if type_ is Request:
        return "request"
    if name in path_params:
        return "path"
    return "query" if is_scalar(type_) else "body"


def path_param_names(path: str) -> set[str]:
    """Extract ``{name}`` placeholders (ignoring an optional ``:converter``).

    取出路径里的 ``{name}`` 占位符，忽略可选的 ``:转换器`` 后缀。
    """
    return {m.group(1) for m in _PATH_PARAM.finditer(path)}


def documented_path(path: str) -> str:
    """Strip Starlette's ``:converter`` suffixes — OpenAPI only knows ``{name}``.

    ``/files/{name:path}`` → ``/files/{name}``。转换器是 Starlette 的路由语法，
    不是 OpenAPI 的；泄漏进文档会让 Swagger UI 把它当成参数名的一部分。
    """
    return _PATH_PLACEHOLDER.sub(r"{\1}", path)
