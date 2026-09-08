"""Request dispatch — execute a handler's precompiled plan and build the response.

请求分发：照着装配期编译好的 :class:`~canary_framework.web.decorator.resolve.HandlerPlan`
取值，调用 handler（必为 ``async def``），再把返回值序列化为 JSON 响应。

这条路径上**没有任何反射**——签名、类型注解、校验器都在启动时算完了，每个请求只是
遍历一个元组、按来源取值、跑已经造好的校验器。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from canary_framework.web.decorator.resolve import HandlerPlan, ParamSpec
from canary_framework.web.error.web import MissingParameterError, RequestValidationError

_MISSING = object()  # 与 None 区分：header 真的传了空串时，None 才表示"没有这一项"


async def dispatch(
    instance: object, fn: Callable[..., object], plan: HandlerPlan, request: Request
) -> Response:
    """Solve *fn*'s parameters from *request*, invoke it, and return a JSON response.

    绑定失败（缺参 / 校验失败）抛出 :class:`RequestValidationError`；它和 handler 抛出的
    其它异常一样交给内置的异常映射处理，最终成为 422。
    """
    try:
        kwargs = {spec.name: await _value_of(spec, request) for spec in plan.params}
    except (ValidationError, MissingParameterError) as exc:
        raise RequestValidationError(exc) from exc
    # handler 必为 async（由 @get/@post 在装配期把关），这里没有第二条同步路径。
    result = await cast("Awaitable[Any]", fn(**kwargs))
    return _to_response(result, plan)


async def _value_of(spec: ParamSpec, request: Request) -> Any:
    """Fetch one parameter from its declared source and validate it.

    按 :class:`ParamSpec` 说好的来源取一个值。取不到时：有缺省值就用缺省值，没有就报缺参。
    ``body`` 与 ``request`` 不走"取不到"这条路——请求体总是存在（哪怕是空的），而
    ``Request`` 对象本来就在手上。
    """
    if spec.location == "request":
        return request
    if spec.location == "body":
        return _validate(spec, await request.json())

    raw = _raw_of(spec, request)
    if raw is _MISSING:
        if not spec.required:
            return spec.default
        raise MissingParameterError(f"missing {spec.location} parameter: {spec.source}")
    return _validate(spec, raw)


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
    raise MissingParameterError(f"unsupported parameter location: {spec.location}")


def _validate(spec: ParamSpec, raw: Any) -> Any:
    """没有转换器就原样透传——没注解、``Any``、或 pydantic 描述不了的类型。"""
    return raw if spec.adapter is None else spec.adapter.validate_python(raw)


def _to_response(result: Any, plan: HandlerPlan) -> Response:
    """Serialise the handler's return value.

    handler 自己造好的响应原样放行——SSE、文件下载、自定义状态码、后台任务都走这里。
    """
    if isinstance(result, Response):
        return result
    if isinstance(result, BaseModel):
        return JSONResponse(result.model_dump(mode="json"))
    if plan.returns is None:
        return JSONResponse(result)
    return JSONResponse(plan.returns.dump_python(result, mode="json"))
