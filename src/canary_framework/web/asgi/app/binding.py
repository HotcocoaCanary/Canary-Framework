"""Binding a request to a method's parameters, and its return value to a response.

把请求绑定到方法的形参，把返回值变成响应。规则在建表时一次定死，请求到来时只做校验。
"""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import types
import typing
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import to_json

from canary_framework.core import DeclarationError
from canary_framework.web.asgi.app.http import HTTPError, Request, Response
from canary_framework.web.asgi.app.routes import Route

_MISSING: Any = inspect.Parameter.empty
_MANY = (list, set, frozenset, tuple)
_JSON = "application/json"


class _Param:
    """一个形参的取值计划。"""

    __slots__ = ("default", "many", "name", "raw", "source", "validate")

    def __init__(self, name: str, source: str, annotation: Any, default: Any, where: str) -> None:
        self.name = name
        self.source = source
        if source == "request":
            return
        self.default = default
        inner = _unwrap(annotation)
        self.many = typing.get_origin(inner) in _MANY or inner in _MANY
        self.raw = source == "body" and inner is bytes
        try:
            adapter = TypeAdapter(annotation)
        except Exception as exc:
            raise DeclarationError(f"{where}: cannot validate {name}: {annotation!r}") from exc
        self.validate = adapter.validate_json if source == "body" else adapter.validate_python


class Endpoint:
    """A bound method, with the plan for calling it from a request.

    一个绑定方法，连同"怎样从请求调用它"的计划。形参按以下顺序归类：

    1. 注解是 :class:`Request` —— 请求对象；
    2. 名字出现在路径模板里 —— 路径参数；
    3. 名字是 ``body`` —— JSON 请求体（注解为 ``bytes`` 时是原始字节）；
    4. 其余 —— 查询参数，有默认值即可选，注解是 ``list[...]`` 之类时取全部同名值。

    没有注解的形参按 ``str``。校验交给 pydantic（请求体按它的 JSON 模式，直接校验原始字节）；
    失败时应答 422，``detail`` 是错误列表。

    ``async def`` 的方法在事件循环里运行；普通 ``def`` 的方法放进线程池，里面的阻塞调用因此
    不会卡住别的请求。

    :raises DeclarationError: 签名无法绑定——``*args`` / ``**kwargs``、路径参数没有对应形参、
        看起来是请求体的形参不叫 ``body``、注解无法解析或无法校验。
    """

    __slots__ = ("_awaits", "_dump", "_params", "call", "name", "status")

    def __init__(self, call: Callable[..., Any], route: Route, path_names: tuple[str, ...]) -> None:
        self.call = call
        self.status = route.status
        self.name = where = getattr(call, "__qualname__", repr(call))
        self._awaits = inspect.iscoroutinefunction(call)
        try:
            hints = typing.get_type_hints(call)
        except Exception as exc:
            raise DeclarationError(f"{where}: cannot resolve its annotations: {exc}") from exc
        self._params = []
        for parameter in inspect.signature(call).parameters.values():
            name = parameter.name
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                raise DeclarationError(f"{where}: *{name} cannot be bound from a request")
            annotation = hints.get(name, Any if name == "body" else str)
            if annotation is Request:
                source = "request"
            elif name in path_names:
                source = "path"
            elif name == "body":
                source = "body"
            else:
                source = "query"
                if _is_structure(_unwrap(annotation)):
                    raise DeclarationError(
                        f"{where}: {name} looks like a request body. "
                        f"Name the parameter 'body', or give it a scalar type to read it "
                        f"from the query string."
                    )
            self._params.append(_Param(name, source, annotation, parameter.default, where))
        unbound = [name for name in path_names if name not in {p.name for p in self._params}]
        if unbound:
            raise DeclarationError(f"{where}: no parameter for the path parameter {unbound[0]!r}")
        self._dump = _dumper(hints.get("return", Any))

    async def __call__(self, request: Request) -> Response:
        """Bind, call, and turn the result into a response.

        绑定形参，调用方法，把返回值变成响应。

        :raises HTTPError: 422，校验失败。
        """
        arguments: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        for param in self._params:
            source = param.source
            if source == "request":
                arguments[param.name] = request
                continue
            if source == "body":
                value: Any = await request.body()
                absent = not value
                if param.raw and not absent:
                    arguments[param.name] = value
                    continue
            elif source == "path":
                value, absent = request.path_params[param.name], False
            else:
                values = request.query.get(param.name)
                absent = values is None
                value = values if param.many else values[-1] if values else None
            if absent:
                if param.default is _MISSING:
                    errors.append({"loc": _loc(param), "msg": "Field required", "type": "missing"})
                else:
                    arguments[param.name] = param.default
                continue
            try:
                arguments[param.name] = param.validate(value)
            except ValidationError as exc:
                for item in exc.errors(
                    include_url=False, include_context=False, include_input=False
                ):
                    loc = [*_loc(param), *item["loc"]]
                    errors.append({"loc": loc, "msg": item["msg"], "type": item["type"]})
        if errors:
            raise HTTPError(422, errors)
        if self._awaits:
            result = await self.call(**arguments)
        else:
            result = await asyncio.to_thread(self.call, **arguments)
        return respond(result, self.status, self._dump)


async def invoke(call: Callable[..., Any], /, *args: Any) -> Any:
    """Call *call*: awaited on the event loop if it is ``async def``, in a thread otherwise.

    调用 *call*：``async def`` 的在事件循环里等待，普通函数放进线程池。
    """
    if inspect.iscoroutinefunction(call):
        return await call(*args)
    return await asyncio.to_thread(call, *args)


def respond(result: Any, status: int = 200, dump: Callable[[Any], bytes] = to_json) -> Response:
    """Turn what a method returned into a response.

    把方法的返回值变成响应：:class:`Response` 原样；``None`` 是空响应（状态码没有另行指定时
    为 204）；其余序列化成 JSON。
    """
    if isinstance(result, Response):
        return result
    if result is None:
        return Response(status=204 if status == 200 else status)
    return Response(dump(result), status=status, media_type=_JSON)


def _dumper(annotation: Any) -> Callable[[Any], bytes]:
    """按返回注解序列化：只序列化，不校验。注解用不上时退回通用的序列化。"""
    if annotation is Any or annotation is None or annotation is Response:
        return to_json
    try:
        adapter = TypeAdapter(annotation)
    except Exception:
        return to_json
    return lambda value: adapter.dump_json(value, warnings=False)


def _loc(param: _Param) -> list[str]:
    return ["body"] if param.source == "body" else [param.source, param.name]


def _unwrap(annotation: Any) -> Any:
    """``X | None`` 里的 ``X``；其余原样。"""
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        rest = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(rest) == 1:
            return rest[0]
    return annotation


def _is_structure(annotation: Any) -> bool:
    if not isinstance(annotation, type):
        return typing.get_origin(annotation) is dict
    return (
        issubclass(annotation, BaseModel | dict)
        or dataclasses.is_dataclass(annotation)
        or typing.is_typeddict(annotation)
    )
