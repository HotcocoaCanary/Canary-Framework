"""OpenAPI document generation and the ``/docs`` page.

文档生成：从装配期编译好的 :class:`~canary_framework.web.decorator.resolve.HandlerPlan`
生成 OpenAPI 3.1 文档；``/docs``（Swagger UI）用 CDN 静态 HTML 渲染，供浏览器直接打开。

**文档和分发读的是同一份计划**——谁从查询串来、谁从请求体来、必填还是可选，这里不再
自己推断一遍。两边的一致因此是构造出来的，而不是"两处都记得调同一对函数"。
"""

from __future__ import annotations

from typing import Any

from canary_framework.web.decorator.resolve import HandlerPlan, ParamSpec, documented_path

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


def build_openapi(title: str, version: str, routes: list[Any]) -> dict[str, Any]:
    """Build the OpenAPI document for the given routes.

    从路由表生成整份文档。``routes`` 是 :class:`~canary_framework.web.core.app.Route`
    的列表——这里只用到 ``method`` / ``path`` / ``plan`` 三项。
    """
    schemas: dict[str, Any] = {}
    paths: dict[str, Any] = {}
    for route in routes:
        # 文档的 key 用归一化后的路径：Starlette 的 ``:converter`` 不属于 OpenAPI。
        paths.setdefault(documented_path(route.path), {})[route.method.lower()] = _operation(
            route.plan, schemas
        )
    doc: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": paths,
    }
    if schemas:
        doc["components"] = {"schemas": schemas}
    return doc


def _operation(plan: HandlerPlan, schemas: dict[str, Any]) -> dict[str, Any]:
    """Describe one handler: its parameters, its request body, its 200 response.

    描述一个 handler。``request`` 来源的形参（整个 ``Request`` 对象）不进文档——它不是
    调用方能提供的东西。
    """
    parameters: list[dict[str, Any]] = []
    request_body: dict[str, Any] | None = None
    for spec in plan.params:
        if spec.location == "request":
            continue
        schema = _schema(spec.adapter, schemas)
        if spec.location == "body":
            request_body = {
                "required": spec.required,
                "content": {"application/json": {"schema": schema}},
            }
            continue
        parameters.append(_parameter(spec, schema))

    operation: dict[str, Any] = {"responses": {"200": _response_doc(plan, schemas)}}
    if parameters:
        operation["parameters"] = parameters
    if request_body:
        operation["requestBody"] = request_body
    return operation


def _parameter(spec: ParamSpec, schema: dict[str, Any]) -> dict[str, Any]:
    """One non-body parameter. ``source`` 已经是协议里的名字（请求头已转成 ``x-token``）。"""
    param: dict[str, Any] = {
        "name": spec.source,
        "in": spec.location,
        "required": spec.required,
        "schema": schema,
    }
    if spec.description:
        param["description"] = spec.description
    return param


def _response_doc(plan: HandlerPlan, schemas: dict[str, Any]) -> dict[str, Any]:
    """Describe the 200 response; handlers returning a ``Response`` declare no JSON schema.

    handler 自己造响应（SSE / 文件 / 自定义状态码）时，媒体类型由它决定，文档不猜。
    """
    if plan.returns_response:
        return {"description": "Successful Response"}
    return {
        "description": "Successful Response",
        "content": {"application/json": {"schema": _schema(plan.returns, schemas)}},
    }


def _schema(adapter: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    """Render *adapter*'s JSON schema, hoisting any ``$defs`` into the shared components.

    没有转换器就是"未约束"（``{}``）：没写注解、注解是 ``Any``、或者这个类型 pydantic
    描述不了——最后那种在装配期已经记过一条 WARNING 点名是哪个 handler，这里不再重复，
    也绝不让它连累整份文档。
    """
    if adapter is None:
        return {}
    schema: dict[str, Any] = adapter.json_schema(ref_template=_REF_TEMPLATE)
    defs = schema.pop("$defs", None)
    if defs:
        schemas.update(defs)
    return schema
