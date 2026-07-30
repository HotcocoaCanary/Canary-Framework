"""Compile validated routes into a Starlette app."""

from __future__ import annotations

from json import JSONDecodeError
from typing import cast

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.routing import Router as StarletteRouter

from canary_framework.common import CanaryConfig, unwrap_optional
from canary_framework.common.routing import ASGIApp
from canary_framework.engine.params import ParameterSpec, RouteAnalysis
from canary_framework.engine.validation import ValidatedRoute

_BOOL_TRUE = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSE = frozenset({"0", "false", "no", "off"})

_SWAGGER_UI_HTML = (
    '<!DOCTYPE html><html><head><title>Swagger UI</title><link rel="stylesheet" href="{swagger_css}"></head>'
    '<body><div id="swagger-ui"></div><script src="{swagger_js}"></script><script>'
    'SwaggerUIBundle({{ url: "{openapi_path}", dom_id: "#swagger-ui" }});</script></body></html>'
)
_REDOC_HTML = (
    '<!DOCTYPE html><html><head><title>ReDoc</title></head><body><div id="redoc"></div>'
    '<script src="{redoc_js}"></script><script>Redoc.init("{openapi_path}", {{}}, '
    'document.getElementById("redoc"));</script></body></html>'
)


class ASGICompiler:
    """Compile validated routes into one Starlette router."""

    def compile(
        self,
        routes: tuple[ValidatedRoute, ...],
        *,
        openapi: dict[str, object],
        config: CanaryConfig,
    ) -> ASGIApp:
        """Return an ASGI app for routes and documentation endpoints."""
        if not routes:
            return cast(ASGIApp, StarletteRouter(routes=[]))

        starlette_routes = [self._build_route(route) for route in routes]
        starlette_routes.extend(self._build_doc_routes(openapi, config))
        return cast(ASGIApp, StarletteRouter(routes=starlette_routes))

    def _build_route(self, validated: ValidatedRoute) -> Route:
        async def endpoint(request: Request) -> Response:
            try:
                arguments = await self._bind_arguments(request, validated.analysis)
            except (JSONDecodeError, UnicodeDecodeError) as exc:
                return JSONResponse({"detail": str(exc)}, status_code=400)
            except (TypeError, ValueError, ValidationError) as exc:
                return JSONResponse({"detail": str(exc)}, status_code=422)

            result = await validated.route.handler(**arguments)
            return self._auto_response(result, validated.route.spec.status_code)

        return Route(
            validated.analysis.starlette_path,
            endpoint=endpoint,
            methods=[validated.route.method],
        )

    async def _bind_arguments(
        self,
        request: Request,
        analysis: RouteAnalysis,
    ) -> dict[str, object]:
        """Bind request values using retained route analysis."""
        arguments: dict[str, object] = {}

        for name in analysis.path_params:
            parameter = analysis.parameters[name]
            arguments[name] = self._convert_param(request.path_params[name], parameter)

        for name in analysis.query_params:
            parameter = analysis.parameters[name]
            if name in request.query_params:
                arguments[name] = self._convert_param(request.query_params[name], parameter)
                continue
            if self._parameter_is_required(parameter):
                raise ValueError(f"Missing required query parameter: {name}")
            arguments[name] = self._parameter_default(parameter)

        if analysis.request_model is not None:
            if analysis.body_param is None:
                raise TypeError("validated route is missing its body parameter")
            body = await request.json()
            model_cls = cast(type[BaseModel], analysis.request_model)
            arguments[analysis.body_param] = model_cls(**cast(dict[str, object], body))

        return arguments

    def _parameter_is_required(self, parameter: ParameterSpec) -> bool:
        field_info = parameter.field_info
        if field_info is None:
            return not parameter.has_default
        required = getattr(field_info, "is_required", None)
        return bool(required()) if callable(required) else False

    def _parameter_default(self, parameter: ParameterSpec) -> object:
        field_info = parameter.field_info
        if field_info is not None:
            getter = getattr(field_info, "get_default", None)
            if callable(getter):
                return getter(call_default_factory=True)
            return field_info.default
        return parameter.default

    def _convert_param(self, value: str, parameter: ParameterSpec) -> object:
        annotation, _nullable = unwrap_optional(parameter.annotation)
        if annotation is None or annotation is str:
            return value
        if annotation is bool:
            lowered = value.lower()
            if lowered in _BOOL_TRUE:
                return True
            if lowered in _BOOL_FALSE:
                return False
            raise ValueError(f"Invalid boolean value: {value!r}")
        if annotation is int:
            return int(value)
        if annotation is float:
            return float(value)
        return value

    def _auto_response(self, result: object, status_code: int) -> Response:
        """Apply explicit Response, tuple status, then route status precedence."""
        if isinstance(result, Response):
            return result
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], int)
            and not isinstance(result[1], bool)
        ):
            body, tuple_status = result
            return self._response_from_body(body, tuple_status)
        return self._response_from_body(result, status_code)

    def _response_from_body(self, body: object, status_code: int) -> Response:
        if isinstance(body, Response):
            body.status_code = status_code
            return body
        if isinstance(body, str):
            return PlainTextResponse(body, status_code=status_code)
        if isinstance(body, BaseModel):
            return JSONResponse(body.model_dump(), status_code=status_code)
        if isinstance(body, (dict, list)):
            return JSONResponse(self._serialize_nested(body), status_code=status_code)
        return PlainTextResponse(str(body), status_code=status_code)

    def _serialize_nested(self, value: object) -> object:
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, dict):
            return {key: self._serialize_nested(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize_nested(item) for item in value]
        return value

    def _build_doc_routes(
        self,
        openapi: dict[str, object],
        config: CanaryConfig,
    ) -> list[Route]:
        async def openapi_endpoint(request: Request) -> JSONResponse:
            del request
            return JSONResponse(openapi)

        swagger_html = _SWAGGER_UI_HTML.format(
            swagger_css=config.docs_swagger_css_cdn,
            swagger_js=config.docs_swagger_js_cdn,
            openapi_path=config.docs_openapi_path,
        )

        redoc_html = _REDOC_HTML.format(
            redoc_js=config.docs_redoc_cdn,
            openapi_path=config.docs_openapi_path,
        )

        async def html_endpoint(request: Request, *, body: str) -> HTMLResponse:
            del request
            return HTMLResponse(body)

        async def swagger_endpoint(request: Request) -> HTMLResponse:
            return await html_endpoint(request, body=swagger_html)

        async def redoc_endpoint(request: Request) -> HTMLResponse:
            return await html_endpoint(request, body=redoc_html)

        return [
            Route(config.docs_openapi_path, endpoint=openapi_endpoint, methods=["GET"]),
            Route(config.docs_swagger_path, endpoint=swagger_endpoint, methods=["GET"]),
            Route(config.docs_redoc_path, endpoint=redoc_endpoint, methods=["GET"]),
        ]


__all__ = ["ASGICompiler"]
