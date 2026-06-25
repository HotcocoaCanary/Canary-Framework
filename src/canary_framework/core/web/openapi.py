"""OpenAPI 3.0.3 schema generator 和文档端点配置。

从RouterMeta列表生成符合OpenAPI 3.0.3规范的schema，并提供 Swagger UI / ReDoc 文档端点。

Generates OpenAPI 3.0.3-compliant schemas from RouterMeta lists
and configures Swagger UI / ReDoc documentation endpoints.
"""

from __future__ import annotations

import warnings
from typing import Any, cast

from pydantic import TypeAdapter
from pydantic.fields import FieldInfo

from canary_framework.common import RouteDef


def _get_schema_for_type(
    annotation: Any,
    schemas_dict: dict[str, object],
    field_info: FieldInfo | None = None,
) -> dict[str, object]:
    """使用 Pydantic TypeAdapter 生成 OpenAPI schema，并提取依赖的 $defs。"""
    from typing import Annotated

    if field_info is not None:
        annotation = Annotated[annotation, field_info]

    try:
        ta = TypeAdapter(annotation)
        schema = ta.json_schema(ref_template="#/components/schemas/{model}")
    except Exception as e:
        warnings.warn(f"Failed to generate schema for type '{annotation}': {e}", stacklevel=2)
        return {"type": "string"}

    if "$defs" in schema:
        schemas_dict.update(cast("dict[str, object]", schema.pop("$defs")))

    if schema.get("type") == "object" and "title" in schema:
        title = str(schema["title"])
        schemas_dict[title] = schema.copy()
        return {"$ref": f"#/components/schemas/{title}"}

    return schema


def generate_openapi_schema(
    route_defs_and_deps: list[tuple[RouteDef, Any]],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
    servers: list[dict[str, str]] | None = None,
    security_schemes: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """从 (RouteDef, EndpointMeta) 列表生成 OpenAPI 3.0.3 schema。"""
    from canary_framework.core.params import EndpointMeta

    schema: dict[str, object] = {
        "openapi": "3.0.3",
        "info": {"title": title, "version": version},
        "paths": {},
        "components": {"schemas": {}},
    }
    if description:
        cast("dict[str, object]", schema["info"])["description"] = description
    if servers:
        schema["servers"] = servers

    components = cast("dict[str, object]", schema["components"])
    if security_schemes:
        components["securitySchemes"] = security_schemes
    schemas_dict = cast("dict[str, object]", components["schemas"])
    paths = cast("dict[str, object]", schema["paths"])

    for route_def, dep in route_defs_and_deps:
        meta = cast(EndpointMeta, dep)
        from starlette.routing import compile_path

        _, starlette_path, _ = compile_path(route_def.path)
        starlette_path = (
            route_def.router_prefix + starlette_path if route_def.router_prefix else starlette_path
        )
        while "//" in starlette_path:
            starlette_path = starlette_path.replace("//", "/")

        operation: dict[str, object] = {}
        if route_def.summary:
            operation["summary"] = route_def.summary
        if route_def.description:
            operation["description"] = route_def.description
        if route_def.deprecated:
            operation["deprecated"] = route_def.deprecated
        if route_def.operation_id:
            operation["operationId"] = route_def.operation_id

        merged_tags = list(dict.fromkeys(route_def.router_tags + route_def.tags))
        if merged_tags:
            operation["tags"] = merged_tags

        parameters: list[dict[str, object]] = []

        def _collect_params(d: EndpointMeta, params_list: list[dict[str, object]]) -> None:
            for param_name, entry in d.path_params.items():
                # Avoid duplicates
                if any(p["name"] == param_name and p["in"] == "path" for p in params_list):
                    continue
                param_schema = _get_schema_for_type(entry[0], schemas_dict, entry[2])
                params_list.append(
                    {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": param_schema,
                    }
                )
            for param_name, entry in d.query_params.items():
                if any(p["name"] == param_name and p["in"] == "query" for p in params_list):
                    continue
                param_schema = _get_schema_for_type(entry[0], schemas_dict, entry[2])
                params_list.append(
                    {
                        "name": param_name,
                        "in": "query",
                        "required": not entry[1],
                        "schema": param_schema,
                    }
                )

        _collect_params(meta, parameters)

        if parameters:
            operation["parameters"] = parameters

        body_model = meta.body_model or route_def.request_model
        if body_model is not None:
            request_schema = _get_schema_for_type(body_model, schemas_dict)
            operation["requestBody"] = {
                "description": getattr(body_model, "__doc__", "") or "",
                "content": {"application/json": {"schema": request_schema}},
            }

        responses: dict[str, object] = dict(route_def.responses)
        if route_def.response_model is not None:
            response_schema = _get_schema_for_type(route_def.response_model, schemas_dict)
            if "200" not in responses:
                responses["200"] = {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": response_schema}},
                }
        operation["responses"] = responses

        _ = paths.setdefault(starlette_path, {})
        cast("dict[str, object]", paths[starlette_path])[route_def.method.lower()] = operation

    return schema


__all__ = ["generate_openapi_schema"]
