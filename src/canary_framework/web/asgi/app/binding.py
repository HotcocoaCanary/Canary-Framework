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


class Param:
    """One parameter of an endpoint: where its value comes from, and what it is validated as.

    接口的一个形参：值从哪里来、按什么类型校验。

    :ivar name: 形参名。
    :ivar source: ``"path"``、``"query"``、``"body"`` 或 ``"request"``（请求对象本身）。
    :ivar annotation: 形参的注解；没有写注解时是 ``str``（``body`` 是 ``Any``）。
    :ivar default: 默认值；没有默认值时是 ``inspect.Parameter.empty``。
    """

    __slots__ = ("_many", "_raw", "_validate", "annotation", "default", "name", "source")

    def __init__(self, name: str, source: str, annotation: Any, default: Any, where: str) -> None:
        self.name = name
        self.source = source
        self.annotation = annotation
        self.default = default
        if source == "request":
            return
        inner = _unwrap(annotation)
        self._many = typing.get_origin(inner) in _MANY or inner in _MANY
        self._raw = source == "body" and inner is bytes
        try:
            adapter = TypeAdapter(annotation)
        except Exception as exc:
            raise DeclarationError(f"{where}: cannot validate {name}: {annotation!r}") from exc
        self._validate = adapter.validate_json if source == "body" else adapter.validate_python

    @property
    def required(self) -> bool:
        """Whether a request must carry it — it has no default.

        请求是否必须带上它，即它没有默认值。
        """
        return self.default is _MISSING

    def __repr__(self) -> str:
        return f"<Param {self.name} from {self.source}>"


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

    建好之后它也是这个接口的一份只读描述，供生成文档、导出客户端之类的用途读取。

    :ivar method: HTTP 方法，大写。
    :ivar path: 完整的路径模板，已带上逐层叠加的前缀，如 ``/api/readers/{reader_id}``。
    :ivar status: 成功时的状态码。返回 ``None`` 而这里是 200 时，实际应答 204。
    :ivar call: 绑定方法本身。
    :ivar name: 绑定方法的限定名，如 ``ReaderApi.show``。
    :ivar params: 形参，按签名的顺序，见 :class:`Param`。
    :ivar returns: 返回注解；没有写时是 ``Any``，``-> None`` 是 ``type(None)``。
    :raises DeclarationError: 签名无法绑定——``*args`` / ``**kwargs``、路径参数没有对应形参、
        看起来是请求体的形参不叫 ``body``、注解无法解析或无法校验。
    """

    __slots__ = (
        "_awaits",
        "_dump",
        "call",
        "method",
        "name",
        "params",
        "path",
        "returns",
        "status",
    )

    def __init__(
        self, call: Callable[..., Any], route: Route, path: str, path_names: tuple[str, ...]
    ) -> None:
        self.call = call
        self.method = route.method
        self.path = path
        self.status = route.status
        self.name = where = getattr(call, "__qualname__", repr(call))
        self._awaits = inspect.iscoroutinefunction(call)
        try:
            hints = typing.get_type_hints(call)
        except Exception as exc:
            raise DeclarationError(f"{where}: cannot resolve its annotations: {exc}") from exc
        params: list[Param] = []
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
            params.append(Param(name, source, annotation, parameter.default, where))
        unbound = [name for name in path_names if name not in {p.name for p in params}]
        if unbound:
            raise DeclarationError(f"{where}: no parameter for the path parameter {unbound[0]!r}")
        self.params = tuple(params)
        self.returns = hints.get("return", Any)
        self._dump = _dumper(self.returns)

    def __repr__(self) -> str:
        return f"<Endpoint {self.method} {self.path} -> {self.name}>"

    async def __call__(self, request: Request) -> Response:
        """Bind, call, and turn the result into a response.

        绑定形参，调用方法，把返回值变成响应。

        :raises HTTPError: 422，校验失败。
        """
        arguments: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        for param in self.params:
            source = param.source
            if source == "request":
                arguments[param.name] = request
                continue
            if source == "body":
                value: Any = await request.body()
                absent = not value
                if param._raw and not absent:
                    arguments[param.name] = value
                    continue
            elif source == "path":
                value, absent = request.path_params[param.name], False
            else:
                values = request.query.get(param.name)
                absent = values is None
                value = values if param._many else values[-1] if values else None
            if absent:
                if param.required:
                    errors.append({"loc": _loc(param), "msg": "Field required", "type": "missing"})
                else:
                    arguments[param.name] = param.default
                continue
            try:
                arguments[param.name] = param._validate(value)
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
    if annotation is Any or annotation is type(None) or annotation is Response:
        return to_json
    try:
        adapter = TypeAdapter(annotation)
    except Exception:
        return to_json
    return lambda value: adapter.dump_json(value, warnings=False)


def _loc(param: Param) -> list[str]:
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
