"""OpenAPI 3.0.3 schema generator 和文档端点配置。

从RouterMeta列表生成符合OpenAPI 3.0.3规范的schema，并提供 Swagger UI / ReDoc 文档端点。

Generates OpenAPI 3.0.3-compliant schemas from RouterMeta lists
and configures Swagger UI / ReDoc documentation endpoints.
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

from canary_framework.common import RouteInfo

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


_registered_schemas: dict[int, str] = {}


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
            name = _generate_schema_name(cast("type[BaseModel]", arg))
            if name in arg_names:
                continue
            arg_names.append(name)
        else:
            arg_names.append(str(arg))
    return cast(str, origin.__name__) + "_" + "_".join(arg_names)


def _register_model_schema(
    model_cls: type[BaseModel],
    schemas_dict: dict[str, object],
) -> str:
    """注册模型 schema，展平 $defs 并返回 schema 引用名。

    使用 ref_template 确保 $ref 指向 #/components/schemas/{model}，
    递归展平所有嵌套的 $defs，按 schema name 去重。
    """
    model_name = _generate_schema_name(model_cls)

    model_id = id(model_cls)
    if model_id in _registered_schemas:
        return _registered_schemas[model_id]

    raw = cast(
        "dict[str, object]",
        model_cls.model_json_schema(ref_template="#/components/schemas/{model}"),
    )
    _flatten_defs(raw, schemas_dict)
    schemas_dict[model_name] = raw
    _registered_schemas[model_id] = model_name

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
    if origin is not None and origin is not UnionType and origin is Literal:
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
        import warnings

        warnings.warn(
            f"Unknown parameter type '{annotation}' — defaulting to 'string' in OpenAPI schema.",
            stacklevel=3,
        )
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
            param_schema = _build_parameter_schema(entry[0], entry[2])  # type: ignore[index]
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
            param_schema = _build_parameter_schema(entry[0], entry[2])  # type: ignore[index]
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
            ref_name = _register_model_schema(info.request_model, schemas_dict)
            operation["requestBody"] = {
                "description": info.request_model.__doc__ or "",
                "content": {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{ref_name}"}}
                },
            }

        responses: dict[str, object] = dict(info.responses)
        if info.response_model is not None:
            ref_name = _register_model_schema(info.response_model, schemas_dict)
            if "200" not in responses:
                responses["200"] = {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {"schema": {"$ref": f"#/components/schemas/{ref_name}"}}
                    },
                }
        operation["responses"] = responses

        _ = paths.setdefault(starlette_path, {})
        cast("dict[str, object]", paths[starlette_path])[info.method.lower()] = operation

    return schema


__all__ = ["generate_openapi_schema"]
