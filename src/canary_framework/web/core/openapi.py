"""OpenAPI document generation and the ``/docs`` / ``/redoc`` / ``/openapi.json`` pages.

文档生成：从路由 + 参数注解 + Pydantic 模型生成 OpenAPI 3.1 文档；``/docs``（Swagger
UI）与 ``/redoc``（Redoc）用 CDN 静态 HTML 渲染，供浏览器直接打开。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter

from canary_framework.web.decorator.resolve import (
    hints_of,
    location_of,
    path_param_names,
    resolve_meta,
)
from canary_framework.web.infra.naming import header_name

_EMPTY = inspect.Parameter.empty
_REF_TEMPLATE = "#/components/schemas/{model}"

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Canary API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });
    };
  </script>
</body>
</html>
"""

REDOC_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Canary API</title>
</head>
<body>
  <redoc spec-url="/openapi.json"></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


def build_openapi(
    title: str,
    version: str,
    routes: list[tuple[str, str, object, Callable[..., object]]],
) -> dict[str, Any]:
    """Build the OpenAPI document for the given routes."""
    schemas: dict[str, Any] = {}
    paths: dict[str, Any] = {}
    for method, path, _instance, fn in routes:
        paths.setdefault(path, {})[method.lower()] = _operation(fn, path, schemas)
    doc: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": paths,
    }
    if schemas:
        doc["components"] = {"schemas": schemas}
    return doc


def _operation(fn: Callable[..., object], path: str, schemas: dict[str, Any]) -> dict[str, Any]:
    hints = hints_of(fn)
    sig = inspect.signature(fn)
    path_params = path_param_names(path)
    parameters: list[dict[str, Any]] = []
    request_body: dict[str, Any] | None = None
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        type_, marker, default = resolve_meta(hints.get(name, param.annotation), param.default)
        location = location_of(type_, marker, name, path_params)
        if location == "request":
            continue
        required = default is _EMPTY
        schema = _schema(type_, schemas)
        if location == "body":
            request_body = {
                "required": required,
                "content": {"application/json": {"schema": schema}},
            }
            continue
        param_name = marker.alias if marker and marker.alias else name
        if location == "header":
            param_name = header_name(param_name)
        param_obj: dict[str, Any] = {
            "name": param_name,
            "in": location,
            "required": required,
            "schema": schema,
        }
        if marker and marker.description:
            param_obj["description"] = marker.description
        parameters.append(param_obj)

    operation: dict[str, Any] = {
        "responses": {
            "200": {
                "description": "Successful Response",
                "content": {
                    "application/json": {"schema": _schema(hints.get("return", _EMPTY), schemas)}
                },
            }
        }
    }
    if parameters:
        operation["parameters"] = parameters
    if request_body:
        operation["requestBody"] = request_body
    return operation


def _schema(annotation: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    if annotation is _EMPTY or annotation is Any or annotation is type(None):
        return {}
    adapter = TypeAdapter(annotation)
    schema = adapter.json_schema(ref_template=_REF_TEMPLATE)
    defs = schema.pop("$defs", None)
    if defs:
        schemas.update(defs)
    return schema
