"""OpenAPI document generation and the ``/docs`` / ``/openapi.json`` pages.

文档生成：从路由 + 参数注解 + Pydantic 模型生成 OpenAPI 3.1 文档；``/docs``（Swagger
UI）用 CDN 静态 HTML 渲染，供浏览器直接打开。
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import PydanticSchemaGenerationError, TypeAdapter
from starlette.responses import Response

from canary_framework.web.decorator.resolve import (
    documented_path,
    hints_of,
    location_of,
    path_param_names,
    unwrap,
)
from canary_framework.web.infra.naming import header_name

_log = logging.getLogger("canary.web.openapi")

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


def build_openapi(
    title: str,
    version: str,
    routes: list[tuple[str, str, object, Callable[..., object]]],
) -> dict[str, Any]:
    """Build the OpenAPI document for the given routes."""
    schemas: dict[str, Any] = {}
    paths: dict[str, Any] = {}
    for method, path, _instance, fn in routes:
        # 文档的 key 用归一化后的路径：Starlette 的 ``:converter`` 不属于 OpenAPI。
        paths.setdefault(documented_path(path), {})[method.lower()] = _operation(fn, path, schemas)
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
        type_, marker = unwrap(hints.get(name, param.annotation))
        location = location_of(type_, marker, name, path_params)
        if location == "request":
            continue
        required = param.default is _EMPTY
        schema = _schema(type_, schemas, fn)
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

    operation: dict[str, Any] = {"responses": {"200": _response_doc(hints, fn, schemas)}}
    if parameters:
        operation["parameters"] = parameters
    if request_body:
        operation["requestBody"] = request_body
    return operation


def _response_doc(
    hints: dict[str, Any], fn: Callable[..., object], schemas: dict[str, Any]
) -> dict[str, Any]:
    """Describe the 200 response; handlers returning a ``Response`` declare no JSON schema."""
    annotation = hints.get("return", _EMPTY)
    if inspect.isclass(annotation) and issubclass(annotation, Response):
        # handler 自己造响应（SSE / 文件 / 自定义状态码），媒体类型由它决定，文档不猜。
        return {"description": "Successful Response"}
    return {
        "description": "Successful Response",
        "content": {"application/json": {"schema": _schema(annotation, schemas, fn)}},
    }


def _schema(
    annotation: Any, schemas: dict[str, Any], fn: Callable[..., object] | None = None
) -> dict[str, Any]:
    """Build the JSON schema for *annotation*, degrading to ``{}`` when it has none.

    一个无法生成 schema 的类型（``TextIO``、``Callable``、自定义容器……）不该让整份
    文档 500——那会连累其余几十个端点。这里退化成"未约束"，并记一条 WARNING 指明
    是哪个 handler 的哪个类型，让问题可见而不是可致命。
    """
    if annotation is _EMPTY or annotation is Any or annotation is type(None):
        return {}
    try:
        schema = TypeAdapter(annotation).json_schema(ref_template=_REF_TEMPLATE)
    except (PydanticSchemaGenerationError, ValueError) as exc:
        where = getattr(fn, "__qualname__", "<unknown handler>") if fn else "<unknown handler>"
        _log.warning(
            "OpenAPI: no schema for %r in %s (%s); documenting it as unconstrained",
            annotation,
            where,
            type(exc).__name__,
        )
        return {}
    defs = schema.pop("$defs", None)
    if defs:
        schemas.update(defs)
    return schema
