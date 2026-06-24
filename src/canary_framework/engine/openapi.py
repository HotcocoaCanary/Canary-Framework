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

from canary_framework.common import RouteInfo


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
    route_infos: list[RouteInfo],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
    servers: list[dict[str, str]] | None = None,
    security_schemes: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """从 RouteInfo 列表生成 OpenAPI 3.0.3 schema。"""
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

    for info in route_infos:
        starlette_path = (
            info.router_prefix + info.starlette_path if info.router_prefix else info.starlette_path
        )
        while "//" in starlette_path:
            starlette_path = starlette_path.replace("//", "/")

        operation: dict[str, object] = {}
        if info.summary:
            operation["summary"] = info.summary
        if info.description:
            operation["description"] = info.description
        if info.deprecated:
            operation["deprecated"] = info.deprecated
        if info.operation_id:
            operation["operationId"] = info.operation_id

        merged_tags = list(dict.fromkeys(info.router_tags + info.tags))
        if merged_tags:
            operation["tags"] = merged_tags

        parameters: list[dict[str, object]] = []
        for param_name in info.path_params:
            entry = info.param_meta.get(param_name, (str, False, None))
            param_schema = _get_schema_for_type(entry[0], schemas_dict, entry[2])  # type: ignore[index]
            parameters.append(
                {
                    "name": param_name,
                    "in": "path",
                    "required": True,
                    "schema": param_schema,
                }
            )
        for param_name in info.query_params:
            entry = info.param_meta.get(param_name, (str, False, None))
            param_schema = _get_schema_for_type(entry[0], schemas_dict, entry[2])  # type: ignore[index]
            parameters.append(
                {
                    "name": param_name,
                    "in": "query",
                    "required": not entry[1],  # type: ignore[index]
                    "schema": param_schema,
                }
            )
        if parameters:
            operation["parameters"] = parameters

        if info.request_model is not None:
            request_schema = _get_schema_for_type(info.request_model, schemas_dict)
            operation["requestBody"] = {
                "description": getattr(info.request_model, "__doc__", "") or "",
                "content": {"application/json": {"schema": request_schema}},
            }

        responses: dict[str, object] = dict(info.responses)
        if info.response_model is not None:
            response_schema = _get_schema_for_type(info.response_model, schemas_dict)
            if "200" not in responses:
                responses["200"] = {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": response_schema}},
                }
        operation["responses"] = responses

        _ = paths.setdefault(starlette_path, {})
        cast("dict[str, object]", paths[starlette_path])[info.method.lower()] = operation

    return schema


__all__ = ["generate_openapi_schema"]
