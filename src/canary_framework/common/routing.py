"""路由路径解析工具。

提供路由路径解析功能，提取路径参数和查询参数。

Route path parsing utilities.

Provides route path parsing to extract path parameters and query parameters.
"""

from __future__ import annotations

import re

_PARAM_PATTERN = r"\{(\w+)\}"


def parse_route_path(path: str) -> tuple[str, list[str], list[str]]:
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

    Parse a route path to extract path parameters and query parameters.

    Path format:
    - Path parameters: {param}, e.g., /op/{kb_id}
    - Query parameters: ?param={param} or #param={param}

    Args:
        path: Route path, e.g., "/op/{kb_id}?count={count}#page={page}"

    Returns:
        (starlette_path, path_params, query_params)
        - starlette_path: Starlette-compatible path, e.g., "/op/{kb_id}"
        - path_params: List of path parameter names, e.g., ["kb_id"]
        - query_params: List of query parameter names, e.g., ["count", "page"]
    """
    base_path = path.split("?")[0].split("#")[0]

    path_params = re.findall(_PARAM_PATTERN, base_path)

    query_params: list[str] = []

    if "?" in path:
        query_part = path.split("?")[1]
        if "#" in query_part:
            query_part = query_part.split("#")[0]
        query_params.extend(re.findall(_PARAM_PATTERN, query_part))

    if "#" in path:
        hash_part = path.split("#")[1]
        if "?" in hash_part:
            hash_part = hash_part.split("?")[0]
        query_params.extend(re.findall(_PARAM_PATTERN, hash_part))

    return base_path, path_params, query_params


__all__ = ["parse_route_path"]
