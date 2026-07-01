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

from canary_framework.common import ResolvedRoute, unwrap_optional

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
            name = _generate_schema_name(cast("type[BaseModel]", arg))
            if name in arg_names:
                continue
            arg_names.append(name)
        else:
            arg_names.append(str(arg))
    return cast(str, origin.__name__) + "_" + "_".join(arg_names)


def _build_model_schema(
    model_cls: Any,
    schemas_dict: dict[str, object],
    registered: dict[int, str],
) -> dict[str, object]:
    """将模型类型转换为 OpenAPI schema dict。

    支持 Pydantic BaseModel 子类（注册到 components/schemas 并返回 $ref）
    以及 list[T] / dict 等泛型容器（生成 inline array / object schema）。

    `registered` 为调用方（`generate_openapi_schema`）持有的调用内局部 registry，
    而非模块级全局状态 —— 确保每次生成互不干扰（修复全局缓存泄漏 bug）。
    Note: `registered` is a call-local registry owned by the caller
    (`generate_openapi_schema`), not module-global state — this ensures
    each generation is independent (fixes the global-cache-leak bug).
    """
    origin: Any = getattr(model_cls, "__origin__", None)

    # list[T] → {"type": "array", "items": ...}
    if origin is list:
        args = getattr(model_cls, "__args__", ())
        item_schema: dict[str, object] = (
            _build_model_schema(args[0], schemas_dict, registered) if args else {}
        )
        return {"type": "array", "items": item_schema}

    # dict[K, V] → {"type": "object"}
    if origin is dict:
        return {"type": "object"}

    # 确定实际 Pydantic 基类（泛型别名取其 __origin__）
    if isinstance(model_cls, type) and issubclass(model_cls, BaseModel):
        pydantic_cls: type[BaseModel] = model_cls
    elif (
        origin is not None
        and origin is not UnionType
        and isinstance(origin, type)
        and issubclass(origin, BaseModel)
    ):
        pydantic_cls = origin
    else:
        return {}

    # 用 model_cls（可能含泛型参数）生成唯一名称，但用基类生成 schema
    model_name = _generate_schema_name(model_cls)
    model_id = id(pydantic_cls)
    if model_id not in registered:
        raw = cast(
            "dict[str, object]",
            pydantic_cls.model_json_schema(ref_template="#/components/schemas/{model}"),
        )
        _flatten_defs(raw, schemas_dict)
        schemas_dict[model_name] = raw
        registered[model_id] = model_name
    return {"$ref": f"#/components/schemas/{model_name}"}


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

    annotation, nullable = unwrap_optional(annotation)
    if nullable:
        schema["nullable"] = True

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
    routes: list[ResolvedRoute],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
    servers: list[dict[str, str]] | None = None,
    security_schemes: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """从 ResolvedRoute 列表生成 OpenAPI 3.0.3 schema。"""
    registered: dict[int, str] = {}
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

    for resolved in routes:
        info = resolved.info
        starlette_path = resolved.full_path
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
            parameters.append(
                {
                    "name": param_name,
                    "in": "path",
                    "required": True,
                    "schema": _build_parameter_schema(entry[0], entry[2]),  # type: ignore[index]
                }
            )
        for param_name in info.query_params:
            entry = info.param_meta.get(param_name, (str, False, None))
            parameters.append(
                {
                    "name": param_name,
                    "in": "query",
                    "required": not entry[1],  # type: ignore[index]
                    "schema": _build_parameter_schema(entry[0], entry[2]),  # type: ignore[index]
                }
            )
        if parameters:
            operation["parameters"] = parameters

        if info.request_model is not None:
            request_schema = _build_model_schema(info.request_model, schemas_dict, registered)
            operation["requestBody"] = {
                "description": getattr(info.request_model, "__doc__", "") or "",
                "content": {"application/json": {"schema": request_schema}},
            }

        responses: dict[str, object] = dict(info.responses)
        if info.response_model is not None:
            response_schema = _build_model_schema(info.response_model, schemas_dict, registered)
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
