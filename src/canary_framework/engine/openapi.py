"""OpenAPI 3.0.3 schema generator.

从RouterMeta列表生成符合OpenAPI 3.0.3规范的schema。

Generates OpenAPI 3.0.3-compliant schemas from RouterMeta lists.
"""

from __future__ import annotations

import inspect
import json
import re
from typing import cast

from pydantic import BaseModel

from canary_framework.common import ROUTE_ATTR, RouterMeta

_TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "str": "string",
    "bool": "boolean",
    "float": "number",
}


def _parse_route_path(path: str) -> tuple[str, list[str], list[str]]:
    """解析路由路径，提取路径参数和查询参数。

    路径格式：
    - 路径参数：{param}，如 /op/{kb_id}
    - 查询参数：?param={param} 或 #param={param}

    Args:
        path: 路由路径，如 "/op/{kb_id}?count={count}#page={page}"

    Returns:
        (starlette_path, path_params, query_params)
        - starlette_path: Starlette兼容的路径，如 "/op/{kb_id}"
        - path_params: 路径参数名称列表，如 ["kb_id"]
        - query_params: 查询参数名称列表，如 ["count", "page"]
    """
    pattern = r"\{(\w+)\}"

    # 分离路径部分和查询参数部分
    base_path = path.split("?")[0].split("#")[0]

    # 提取路径参数（在基础路径中的 {param}）
    path_params = re.findall(pattern, base_path)

    # 提取查询参数（在 ? 或 # 后面的 {param}）
    query_params: list[str] = []

    # 查找 ? 后的查询参数
    if "?" in path:
        query_part = path.split("?")[1]
        # 去掉 # 后面的部分
        if "#" in query_part:
            query_part = query_part.split("#")[0]
        query_params.extend(re.findall(pattern, query_part))

    # 查找 # 后的查询参数
    if "#" in path:
        hash_part = path.split("#")[1]
        # 去掉 ? 后面的部分（如果 # 在 ? 前面）
        if "?" in hash_part:
            hash_part = hash_part.split("?")[0]
        query_params.extend(re.findall(pattern, hash_part))

    return base_path, path_params, query_params


def _get_type_name(param_type: type | None) -> str:
    """获取类型名称。

    Args:
        param_type: 参数类型

    Returns:
        类型名称字符串
    """
    if param_type is inspect.Parameter.empty or param_type is None:
        return "string"
    if hasattr(param_type, "__name__"):
        return param_type.__name__
    return str(param_type)


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

            # 解析路径，提取路径参数和查询参数
            starlette_path, path_param_names, query_param_names = _parse_route_path(path)

            sig = inspect.signature(route_fn)
            param_types = {
                name: param.annotation for name, param in sig.parameters.items() if name != "self"
            }

            # 生成路径参数的OpenAPI定义
            for param_name in path_param_names:
                param_type = _get_type_name(param_types.get(param_name))
                openapi_type = _TYPE_MAP.get(param_type, "string")
                path_param: dict[str, object] = {
                    "name": param_name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": openapi_type},
                }
                parameters.append(path_param)

            # 生成查询参数的OpenAPI定义
            for param_name in query_param_names:
                param_type = _get_type_name(param_types.get(param_name))
                openapi_type = _TYPE_MAP.get(param_type, "string")
                query_param: dict[str, object] = {
                    "name": param_name,
                    "in": "query",
                    "required": False,
                    "schema": {"type": openapi_type},
                }
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

            _ = paths.setdefault(starlette_path, {})
            cast("dict[str, object]", paths[starlette_path])[method] = operation

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
