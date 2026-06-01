"""OpenAPI 3.0.3 schema generator.

从RouterMeta列表生成符合OpenAPI 3.0.3规范的schema。

Generates OpenAPI 3.0.3-compliant schemas from RouterMeta lists.
"""

from __future__ import annotations

import json
from typing import cast

from pydantic import BaseModel

from canary_framework.common import ROUTE_ATTR, RouterMeta

_TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "str": "string",
    "bool": "boolean",
    "float": "number",
}


def generate_openapi_schema(
    router_metas: list[RouterMeta],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
) -> dict[str, object]:
    """生成OpenAPI 3.0.3 schema。

    从RouterMeta列表生成完整的OpenAPI schema，包括路径、参数、
    请求体、响应和组件定义。

    Args:
        router_metas: 路由器元数据列表。
        title: API标题。
        version: API版本。
        description: API描述。

    Returns:
        OpenAPI schema字典。

    Generate OpenAPI 3.0.3 schema.

    Generates a complete OpenAPI schema from RouterMeta list, including
    paths, parameters, request bodies, responses, and component definitions.

    Args:
        router_metas: List of router metadata.
        title: API title.
        version: API version.
        description: API description.

    Returns:
        OpenAPI schema dictionary.
    """
    schema: dict[str, object] = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": version,
        },
        "paths": {},
        "components": {"schemas": {}},
    }
    if description:
        info_dict = cast("dict[str, object]", schema["info"])
        info_dict["description"] = description

    _added_schemas: set[str] = set()
    components = cast("dict[str, object]", schema["components"])
    schemas_dict = cast("dict[str, object]", components["schemas"])
    paths = cast("dict[str, object]", schema["paths"])

    for meta in router_metas:
        router_tags = meta.tags or []
        prefix = meta.prefix or ""

        for route_fn in meta.routes:
            raw_info = cast("dict[str, object]", getattr(route_fn, ROUTE_ATTR, {}))
            if not raw_info:
                continue

            method = cast(str, raw_info.get("method", "get")).lower()
            path = prefix + cast(str, raw_info.get("path", "/"))
            summary = raw_info.get("summary")
            description_val = raw_info.get("description")
            deprecated = cast("bool", raw_info.get("deprecated", False))
            operation_id = raw_info.get("operation_id")
            route_tags = cast("list[str]", raw_info.get("tags") or [])
            response_model = raw_info.get("response_model")
            request_model = raw_info.get("request_model")

            merged_tags = list(dict.fromkeys(router_tags + route_tags))

            operation: dict[str, object] = {}
            if summary:
                operation["summary"] = summary
            if description_val:
                operation["description"] = description_val
            if deprecated:
                operation["deprecated"] = deprecated
            if operation_id:
                operation["operationId"] = operation_id
            if merged_tags:
                operation["tags"] = merged_tags

            parameters: list[dict[str, object]] = []
            path_params = cast("dict[str, object]", raw_info.get("path_params") or {})
            for param_name, param_info in path_params.items():
                param_info_dict = cast("dict[str, object]", param_info)
                param_type = _TYPE_MAP.get(
                    cast(str, param_info_dict.get("type", "string")), "string"
                )
                path_param: dict[str, object] = {
                    "name": param_name,
                    "in": "path",
                    "required": param_info_dict.get("required", True),
                    "schema": {"type": param_type},
                }
                if param_info_dict.get("description"):
                    path_param["description"] = param_info_dict["description"]
                parameters.append(path_param)

            query_params = cast("dict[str, object]", raw_info.get("query_params") or {})
            for param_name, param_info in query_params.items():
                param_info_dict = cast("dict[str, object]", param_info)
                param_type = _TYPE_MAP.get(
                    cast(str, param_info_dict.get("type", "string")), "string"
                )
                query_param: dict[str, object] = {
                    "name": param_name,
                    "in": "query",
                    "required": param_info_dict.get("required", False),
                    "schema": {"type": param_type},
                }
                if param_info_dict.get("description"):
                    query_param["description"] = param_info_dict["description"]
                parameters.append(query_param)

            if parameters:
                operation["parameters"] = parameters

            if request_model is not None:
                model_cls = cast("type[BaseModel]", request_model)
                model_schema = cast("dict[str, object]", model_cls.model_json_schema())
                model_name = model_cls.__name__
                if model_name not in _added_schemas:
                    schemas_dict[model_name] = model_schema
                    _added_schemas.add(model_name)
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{model_name}"}
                        }
                    }
                }

            user_responses = cast("dict[str, object]", raw_info.get("responses") or {})
            responses: dict[str, object] = dict(user_responses)

            if response_model is not None:
                model_cls = cast("type[BaseModel]", response_model)
                model_schema = cast("dict[str, object]", model_cls.model_json_schema())
                model_name = model_cls.__name__
                if model_name not in _added_schemas:
                    schemas_dict[model_name] = model_schema
                    _added_schemas.add(model_name)
                if "200" not in responses:
                    responses["200"] = {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{model_name}"}
                            }
                        },
                    }

            operation["responses"] = responses

            _ = paths.setdefault(path, {})
            cast("dict[str, object]", paths[path])[method] = operation

    return schema


def get_openapi_json(
    router_metas: list[RouterMeta],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
) -> str:
    """获取OpenAPI JSON字符串。

    生成OpenAPI schema并返回JSON字符串。

    Args:
        router_metas: 路由器元数据列表。
        title: API标题。
        version: API版本。
        description: API描述。

    Returns:
        OpenAPI JSON字符串。

    Get OpenAPI JSON string.

    Generates OpenAPI schema and returns JSON string.

    Args:
        router_metas: List of router metadata.
        title: API title.
        version: API version.
        description: API description.

    Returns:
        OpenAPI JSON string.
    """
    return json.dumps(
        generate_openapi_schema(router_metas, title, version, description),
        ensure_ascii=False,
    )


__all__ = [
    "generate_openapi_schema",
    "get_openapi_json",
]
