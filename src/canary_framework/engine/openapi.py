"""OpenAPI 3.0.3 schema generator.

从RouterMeta列表生成符合OpenAPI 3.0.3规范的schema。

Generates OpenAPI 3.0.3-compliant schemas from RouterMeta lists.
"""

from __future__ import annotations

from datetime import date, datetime
from datetime import time as _time
from enum import Enum
from types import UnionType
from typing import Any, Literal, cast, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from canary_framework.common import ROUTE_ATTR, ServiceMeta
from canary_framework.common.routing import parse_route_path
from canary_framework.engine.params import resolve_params

_TYPE_MAP: dict[str, str] = {
    "int": "integer",
    "str": "string",
    "bool": "boolean",
    "float": "number",
}

_TYPE_FORMAT_MAP: dict[type, str] = {
    datetime: "date-time",
    date: "date",
    _time: "time",
    UUID: "uuid",
    bytes: "byte",
}


def _flatten_defs(schema: dict[str, object], schemas_dict: dict[str, object]) -> None:
    """递归提取并展平 schema 中的 $defs 到 schemas_dict。"""
    if "$defs" not in schema:
        return
    defs = cast("dict[str, object]", schema.pop("$defs"))
    for def_name, def_schema in defs.items():
        def_schema_dict = cast("dict[str, object]", def_schema)
        _flatten_defs(def_schema_dict, schemas_dict)
        if def_name not in schemas_dict:
            schemas_dict[def_name] = def_schema_dict


def _generate_schema_name(model_cls: type[BaseModel]) -> str:
    """生成稳定可读的 schema 名称，格式: Origin_Arg（如 R_KbResponse、R_str）。

    泛型模型 R[str] 和 R[int] 的 __name__ 都是 "R"，仅用 __name__ 无法区分。
    通过检测 __origin__ 和 __args__ 生成 "R_str" / "R_int" 等唯一名称。
    """
    origin: Any = getattr(model_cls, "__origin__", None)
    if origin is None:
        return model_cls.__name__

    args = getattr(model_cls, "__args__", ())
    arg_names: list[str] = []
    for arg in args:
        if arg is type(None):
            continue
        if hasattr(arg, "__name__"):
            arg_names.append(cast(str, arg.__name__))
        elif hasattr(arg, "__origin__"):
            arg_names.append(_generate_schema_name(cast("type[BaseModel]", arg)))
        else:
            arg_names.append(str(arg))
    return cast(str, origin.__name__) + "_" + "_".join(arg_names)


def _register_model_schema(
    model_cls: type[BaseModel],
    schemas_dict: dict[str, object],
    added_model_ids: set[int],
) -> str:
    """注册模型 schema，展平 $defs 并返回 schema 引用名。

    使用 ref_template 确保 $ref 指向 #/components/schemas/{model}，
    递归展平所有嵌套的 $defs，用 id() 去重避免泛型命名冲突。
    """
    model_id = id(model_cls)
    model_name = _generate_schema_name(model_cls)

    raw = cast(
        "dict[str, object]",
        model_cls.model_json_schema(ref_template="#/components/schemas/{model}"),
    )

    _flatten_defs(raw, schemas_dict)

    if model_id not in added_model_ids:
        schemas_dict[model_name] = raw
        added_model_ids.add(model_id)

    return model_name


def _is_optional(annotation: Any) -> bool:
    """检测类型是否为 Optional[T] 或 T | None。"""
    origin = get_origin(annotation)
    if origin is None:
        return False
    if origin is UnionType:
        args = get_args(annotation)
        return type(None) in args
    return False


def _unwrap_optional(annotation: Any) -> Any:
    """从 Optional[T] 或 T | None 中提取 T。"""
    args = get_args(annotation)
    if args:
        for arg in args:
            if arg is not type(None):
                return arg
    return annotation


def _get_enum_values(annotation: Any) -> list[object] | None:
    """尝试从枚举或 Literal 类型中提取值列表。"""
    origin = get_origin(annotation)
    if (
        origin is not None
        and origin is not UnionType
        and (origin is Literal or str(origin).startswith("typing.Literal"))
    ):
        return list(get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [e.value for e in annotation]
    return None


def _build_parameter_schema(
    annotation: Any,
    field_info: FieldInfo | None = None,
) -> dict[str, object]:
    """从类型注解构建 OpenAPI 参数 schema。

    支持 Optional、Literal/Enum、Field 约束、datetime/date/uuid 格式。
    """
    schema: dict[str, object] = {}

    if _is_optional(annotation):
        inner = _unwrap_optional(annotation)
        schema["nullable"] = True
        annotation = inner

    enum_values = _get_enum_values(annotation)

    if enum_values is not None:
        if all(isinstance(v, bool) for v in enum_values):
            openapi_type = "boolean"
        elif all(isinstance(v, int) for v in enum_values):
            openapi_type = "integer"
        elif all(isinstance(v, float) for v in enum_values):
            openapi_type = "number"
        else:
            openapi_type = "string"
        schema["type"] = openapi_type
        schema["enum"] = enum_values
    elif hasattr(annotation, "__name__"):
        type_name = annotation.__name__
        openapi_type = _TYPE_MAP.get(type_name, "string")
        schema["type"] = openapi_type

        if annotation in _TYPE_FORMAT_MAP:
            schema["format"] = _TYPE_FORMAT_MAP[annotation]
    elif annotation is bytes:
        schema["type"] = "string"
        schema["format"] = "byte"
    else:
        schema["type"] = "string"

    if field_info is not None:
        _apply_field_metadata(schema, field_info)
        _apply_field_constraints(schema, field_info)

    return schema


def _apply_field_metadata(schema: dict[str, object], field_info: FieldInfo) -> None:
    """从 FieldInfo 提取文档元数据：description, title, deprecated, examples。"""
    if field_info.description:
        schema["description"] = field_info.description
    if field_info.title:
        schema["title"] = field_info.title
    if field_info.deprecated:
        schema["deprecated"] = True
    examples = getattr(field_info, "examples", None)
    if examples and isinstance(examples, list) and examples:
        schema["example"] = examples[0]


def _apply_field_constraints(schema: dict[str, object], field_info: FieldInfo) -> None:
    """从 FieldInfo.metadata 中提取 Pydantic v2 约束对象。

    Pydantic v2 将 ge/le/gt/lt/min_length/max_length/pattern 等约束
    存储在 field_info.metadata 列表中的约束对象上，而非 FieldInfo 的直接属性。
    遍历 metadata 检查每个对象的 hasattr 是正确方式。
    """
    for meta in field_info.metadata:
        for attr, key in [
            ("min_length", "minLength"),
            ("max_length", "maxLength"),
            ("pattern", "pattern"),
            ("ge", "minimum"),
            ("gt", "exclusiveMinimum"),
            ("le", "maximum"),
            ("lt", "exclusiveMaximum"),
            ("multiple_of", "multipleOf"),
        ]:
            if hasattr(meta, attr):
                schema[key] = getattr(meta, attr)


def generate_openapi_schema(
    router_metas: list[ServiceMeta],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
    servers: list[dict[str, str]] | None = None,
    security_schemes: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """生成OpenAPI 3.0.3 schema。

    从RouterMeta列表生成完整的OpenAPI schema，包括路径、参数、
    请求体、响应和组件定义。

    Args:
        :param security_schemes:
        :param router_metas: 路由器元数据列表。
        :param title: API标题。
        :param version: API版本。
        :param description: API描述。
        :param servers: 服务器列表，如 [{"url": "http://localhost:8000"}]

    Returns:
        OpenAPI schema字典。
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
        cast("dict[str, object]", schema["info"])["description"] = description
    if servers:
        schema["servers"] = servers

    added_schema_ids: set[int] = set()
    components = cast("dict[str, object]", schema["components"])
    if security_schemes:
        components["securitySchemes"] = security_schemes
    schemas_dict = cast("dict[str, object]", components["schemas"])
    paths = cast("dict[str, object]", schema["paths"])

    for meta in router_metas:
        router_tags = meta.tags or []
        prefix = meta.prefix or ""

        for route_fn in meta.routes:
            raw_info = getattr(route_fn, ROUTE_ATTR, {})
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

            starlette_path, path_param_names, query_param_names = parse_route_path(path)

            param_meta = resolve_params(route_fn)

            for param_name in path_param_names:
                annotation, _, field_info = param_meta.get(param_name, (str, False, None))
                param_schema = _build_parameter_schema(annotation, field_info)
                path_param: dict[str, object] = {
                    "name": param_name,
                    "in": "path",
                    "required": True,
                    "schema": param_schema,
                }
                parameters.append(path_param)

            for param_name in query_param_names:
                annotation, has_default, field_info = param_meta.get(param_name, (str, False, None))
                param_schema = _build_parameter_schema(annotation, field_info)
                query_param: dict[str, object] = {
                    "name": param_name,
                    "in": "query",
                    "required": not has_default,
                    "schema": param_schema,
                }
                parameters.append(query_param)

            if parameters:
                operation["parameters"] = parameters

            if request_model is not None:
                model_cls = cast("type[BaseModel]", request_model)
                ref_name = _register_model_schema(model_cls, schemas_dict, added_schema_ids)
                operation["requestBody"] = {
                    "description": model_cls.__doc__ or "",
                    "content": {
                        "application/json": {"schema": {"$ref": f"#/components/schemas/{ref_name}"}}
                    },
                }

            user_responses = cast("dict[str, object]", raw_info.get("responses") or {})
            responses: dict[str, object] = dict(user_responses)

            if response_model is not None:
                model_cls = cast("type[BaseModel]", response_model)
                ref_name = _register_model_schema(model_cls, schemas_dict, added_schema_ids)
                if "200" not in responses:
                    responses["200"] = {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{ref_name}"}
                            }
                        },
                    }

            operation["responses"] = responses

            _ = paths.setdefault(starlette_path, {})
            cast("dict[str, object]", paths[starlette_path])[method] = operation

    return schema


__all__ = ["generate_openapi_schema"]
