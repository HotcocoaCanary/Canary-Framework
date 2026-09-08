"""Request dispatch — execute a handler's precompiled plan and build the response.

请求分发：照着装配期编译好的 :class:`~canary_framework.web.decorator.resolve.HandlerPlan`
取值，调用 handler（必为 ``async def``），再把返回值序列化为 JSON 响应。

这条路径上**没有任何反射**——签名、类型注解、校验器都在启动时算完了，每个请求只是
遍历一个元组、按来源取值、跑已经造好的校验器。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from canary_framework.web.decorator.resolve import HandlerPlan, ParamSpec
from canary_framework.web.error.web import (
    BindingError,
    RequestValidationError,
    ResponseValidationError,
)

_MISSING = object()  # 与 None 区分：header 真的传了空串时，None 才表示"没有这一项"


async def dispatch(
    instance: object,
    fn: Callable[..., object],
    plan: HandlerPlan,
    request: Request,
    status_code: int = 200,
    no_body: bool = False,
) -> Response:
    """Solve *fn*'s parameters from *request*, invoke it, and return a JSON response.

    绑定失败（缺参 / 校验失败）抛出 :class:`RequestValidationError`；它和 handler 抛出的
    其它异常一样交给内置的异常映射处理，最终成为 422。
    """
    try:
        kwargs = {spec.name: await _value_of(spec, request) for spec in plan.params}
    except (ValidationError, BindingError) as exc:
        raise RequestValidationError(exc) from exc
    # handler 必为 async（由 @get/@post 在装配期把关），这里没有第二条同步路径。
    result = await cast("Awaitable[Any]", fn(**kwargs))
    return _to_response(result, plan, fn, status_code, no_body)


async def _value_of(spec: ParamSpec, request: Request) -> Any:
    """Fetch one parameter from its declared source and validate it.

    按 :class:`ParamSpec` 说好的来源取一个值。取不到时：有缺省值就用缺省值，没有就报缺参。
    ``body`` 与 ``request`` 不走"取不到"这条路——请求体总是存在（哪怕是空的），而
    ``Request`` 对象本来就在手上。
    """
    if spec.location == "request":
        return request
    if spec.location == "body":
        body = await _body_of(spec, request)
        # 没有请求体、而形参有缺省值——这就是"可选请求体"。
        return spec.default if body is _MISSING else _validate(spec, body)

    raw = _raw_of(spec, request)
    if raw is _MISSING:
        if not spec.required:
            return spec.default
        raise BindingError(f"missing {spec.location} parameter: {spec.source}")
    return _validate(spec, raw)


async def _body_of(spec: ParamSpec, request: Request) -> Any:
    """Read and parse the request body, turning every failure into a 422.

    请求体的三条失败路径从前全掉进 500：空 body、不是合法 JSON、发成了表单。原因是
    ``request.json()`` 抛的是 ``JSONDecodeError``，而分发只接住了字段校验失败那一种。
    它们统统是**调用方**把请求发错了，该是 422。

    先读原始字节再解析，是为了把"没有请求体"和"请求体是 null"分开——只有前者才能落到
    形参的缺省值上，``item: Item | None = None`` 这种可选请求体因此才写得出来。
    """
    raw = await request.body()
    if not raw.strip():
        if not spec.required:
            return _MISSING
        raise BindingError("missing request body")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BindingError(f"request body is not valid JSON: {exc}") from exc


def _raw_of(spec: ParamSpec, request: Request) -> Any:
    """Pull the still-unvalidated value out of the request, or :data:`_MISSING`.

    从请求里取出未经校验的原始值。查询串的多值参数用 ``getlist``——``?tag=a&tag=b``
    要还原成 ``["a", "b"]``，而 ``get`` 只会给最后一个。
    """
    if spec.location == "path":
        return request.path_params.get(spec.source, _MISSING)
    if spec.location == "query":
        if spec.multi:
            values = request.query_params.getlist(spec.source)
            return values if values else _MISSING
        return request.query_params.get(spec.source, _MISSING)
    if spec.location == "header":
        return request.headers.get(spec.source, _MISSING)
    if spec.location == "cookie":
        return request.cookies.get(spec.source, _MISSING)
    raise BindingError(f"unsupported parameter location: {spec.location}")


def _validate(spec: ParamSpec, raw: Any) -> Any:
    """没有转换器就原样透传——没注解、``Any``、或 pydantic 描述不了的类型。"""
    return raw if spec.adapter is None else spec.adapter.validate_python(raw)


def _to_response(
    result: Any,
    plan: HandlerPlan,
    fn: Callable[..., object],
    status_code: int,
    no_body: bool,
) -> Response:
    """Check the return value against its declared type, then serialise it.

    handler 自己造好的响应原样放行——SSE、文件下载、后台任务、以及需要按情况变化的状态码
    都走这里，它自己的状态码说了算。

    否则用声明的 ``status_code``。``204`` / ``304`` 按 HTTP 规范不能带响应体，发一个空响应
    而不是 JSON 的 ``null``。

    有返回注解就**先校验再序列化**：``/docs`` 照着这个注解向调用方承诺了响应的形状，
    不校验的话，声明 ``-> Book`` 而实际少发一个字段没有任何人会喊一声。校验失败是服务端
    的 bug，所以抛 :class:`ResponseValidationError` 走 500，而不是伪装成客户端的错。
    """
    if isinstance(result, Response):
        return result
    if no_body:
        return Response(status_code=status_code)
    if plan.returns is None:
        # 没有注解 / 注解是 Any：没什么可校验的，模型自己知道怎么变成 JSON。
        if isinstance(result, BaseModel):
            return JSONResponse(result.model_dump(mode="json"), status_code=status_code)
        return JSONResponse(result, status_code=status_code)
    try:
        validated = plan.returns.validate_python(result)
    except ValidationError as exc:
        raise ResponseValidationError(str(getattr(fn, "__qualname__", fn)), exc) from exc
    return JSONResponse(plan.returns.dump_python(validated, mode="json"), status_code=status_code)
