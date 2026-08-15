"""Request dispatch — bind handler parameters and build a JSON response.

请求分发：把一次请求的路径 / 查询 / 请求头 / 请求体按 handler 签名绑定为关键字参数，
调用 handler（同步 / 异步自动判断），再把返回值校验后序列化为 JSON 响应。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_origin

from pydantic import BaseModel, TypeAdapter, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from canary_framework.web.decorator.resolve import hints_of, location_of, resolve_meta
from canary_framework.web.error.web import MissingParameterError
from canary_framework.web.infra.naming import header_name

_EMPTY = inspect.Parameter.empty


async def dispatch(instance: object, fn: Callable[..., object], request: Request) -> Response:
    """Solve *fn*'s parameters from *request*, invoke it, and return a JSON response.

    绑定失败（缺参 / 校验失败）映射为 422；handler 抛出的其它异常继续向上传播，
    由上层（如 uvicorn / TestClient）处理。
    """
    hints = hints_of(fn)
    try:
        kwargs = await _solve(fn, request, hints)
    except (ValidationError, MissingParameterError) as exc:
        return JSONResponse({"detail": _detail(exc)}, status_code=422)
    result = fn(**kwargs)
    if inspect.isawaitable(result):
        result = await result
    return _to_response(result, hints.get("return", _EMPTY))


async def _solve(
    fn: Callable[..., object], request: Request, hints: dict[str, Any]
) -> dict[str, Any]:
    sig = inspect.signature(fn)
    path_params = set(request.path_params)
    values: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        type_, marker, default = resolve_meta(hints.get(name, param.annotation), param.default)
        location = location_of(type_, marker, name, path_params)
        values[name] = await _resolve_one(name, type_, marker, location, request, default)
    return values


async def _resolve_one(
    name: str,
    type_: Any,
    marker: Any,
    location: str,
    request: Request,
    default: Any,
) -> Any:
    if location == "request":
        return request
    alias = marker.alias if marker and marker.alias else name
    if location == "body":
        return _coerce(type_, await request.json())
    if location == "path":
        return _coerce(type_, request.path_params.get(name))
    if location == "query":
        return _from_query(name, type_, request, default)
    if location in ("header", "cookie"):
        raw = (
            request.headers.get(header_name(alias))
            if location == "header"
            else request.cookies.get(alias)
        )
        if raw is None:
            if default is not _EMPTY:
                return default
            raise MissingParameterError(f"missing {location} parameter: {alias}")
        return _coerce(type_, raw)
    raise MissingParameterError(f"unsupported parameter location: {location}")


def _from_query(name: str, type_: Any, request: Request, default: Any) -> Any:
    if get_origin(type_) is list:
        values = request.query_params.getlist(name)
        if values:
            return _coerce(type_, values)
        if default is not _EMPTY:
            return default
        raise MissingParameterError(f"missing query parameter: {name}")
    raw = request.query_params.get(name)
    if raw is None:
        if default is not _EMPTY:
            return default
        raise MissingParameterError(f"missing query parameter: {name}")
    return _coerce(type_, raw)


def _coerce(type_: Any, raw: Any) -> Any:
    if type_ is _EMPTY or type_ is Any or type_ is type(None):
        return raw
    return TypeAdapter(type_).validate_python(raw)


def _to_response(result: Any, return_ann: Any) -> JSONResponse:
    if isinstance(result, BaseModel):
        return JSONResponse(result.model_dump(mode="json"))
    if return_ann is _EMPTY or return_ann is Any or return_ann is type(None):
        return JSONResponse(result)
    return JSONResponse(TypeAdapter(return_ann).dump_python(result, mode="json"))


def _detail(exc: ValidationError | MissingParameterError) -> Any:
    if isinstance(exc, ValidationError):
        return exc.errors(include_url=False)
    return str(exc)
