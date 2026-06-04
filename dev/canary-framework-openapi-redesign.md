# Canary Framework OpenAPI 模块重构设计方案

> **版本**: 针对 `canary_framework==0.4.10`
> **日期**: 2026-06-04
> **参考**: FastAPI 源码中 `fastapi/openapi/` 模块设计

---

## 目录

1. [设计目标](#设计目标)
2. [架构概览](#架构概览)
3. [核心模块设计](#核心模块设计)
   - [3.1 SchemaRegistry — Schema 注册中心](#31-schemaregistry--schema-注册中心)
   - [3.2 OpenAPIParams — 参数类型映射](#32-openapiparams--参数类型映射)
   - [3.3 OpenAPIGenerator — 生成器](#33-openapigenerator--生成器)
   - [3.4 路由 URL 修复](#34-路由-url-修复)
4. [API 设计](#api-设计)
5. [与现有实现的对比](#与现有实现的对比)
6. [迁移指南](#迁移指南)

---

## 设计目标

1. **零破坏性修复**：`@router` / `@post` / `@get` 等装饰器 API 不变
2. **完整的 Pydantic v2 集成**：正确展平泛型模型的 `$defs`，处理 `$ref` 路径
3. **FastAPI 级别的文档质量**：约束、枚举、格式字段全部展示
4. **可配置**：servers、security schemes、CDN 路径均可配置
5. **一致性**：Swagger 文档中的 URL 与路由实际 URL 一致

---

## 架构概览

```
┌──────────────────────────────────────────────────────────┐
│                     业务代码层                             │
│  @router(prefix="/kb")                                   │
│  class KBRouter:                                         │
│      @post(path="/", response_model=R[KbResponse])        │
│      def create(self, request: CreateKbRequest): ...      │
└──────────────────────────┬───────────────────────────────┘
                           │ ROUTE_ATTR 元数据
                           ▼
┌──────────────────────────────────────────────────────────┐
│               SchemaRegistry (新增)                       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ • 按 model id() 去重，解决泛型命名冲突              │ │
│  │ • ref_template='#/components/schemas/{model}'       │ │
│  │ • 递归展平 $defs → components/schemas/              │ │
│  │ • 生成稳定可读的 schema 名称                        │ │
│  │ • 处理循环引用                                      │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│            OpenAPIGenerator (重构)                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ • OpenAPIParams: Pydantic FieldInfo → OpenAPI param  │ │
│  │ • 约束映射: minLength, pattern, ge, le, enum, ...   │ │
│  │ • 类型映射: datetime→"date-time", uuid→"uuid", ...  │ │
│  │ • 可配置: servers, securitySchemes                  │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│              OpenAPI 3.0.3 JSON Document                   │
│  {                                                        │
│    "openapi": "3.0.3",                                    │
│    "paths": { "/kb/": { ... } },                          │
│    "components": {                                        │
│      "schemas": {                                         │
│        "R_KbResponse": { ... },                           │
│        "KbResponse": { ... },                             │
│        "CreateKbRequest": { ... }                         │
│      }                                                    │
│    }                                                      │
│  }                                                        │
└──────────────────────────────────────────────────────────┘
```

### 文件结构变更

```
canary_framework/engine/
├── openapi.py          → 删除或重命名为 openapi_v1_deprecated.py
├── schema_registry.py  → 新增：Schema 注册与展平
├── openapi_params.py   → 新增：Pydantic → OpenAPI 类型映射
└── openapi_v2.py       → 新增：重构后的生成器

canary_framework/core/
├── module.py           → 修改：路由挂载逻辑
└── router.py           → 修改：移除双重前缀
```

---

## 核心模块设计

### 3.1 SchemaRegistry — Schema 注册中心

**职责**：
- 接收 Pydantic 模型（含泛型），生成 OpenAPI 兼容的 schema
- 自动展平 `$defs` 并改写 `$ref`
- 按模型身份去重，生成稳定命名

```python
# engine/schema_registry.py

from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema


class SchemaRegistry:
    """OpenAPI Schema 注册中心。

    核心设计：
    1. 去重：使用 id(model_cls) 而非 __name__——R[str] ≠ R[int]
    2. 展平：递归提取 $defs 到 components/schemas/
    3. 重写 $ref：通过 GenerateJsonSchema 的 ref_template 参数
    4. 命名：泛型生成 "Origin_Arg1_Arg2" 格式，可读且唯一
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}
        self._model_ids: dict[int, str] = {}

    def register(self, model_cls: type[BaseModel]) -> str:
        """注册一个模型及其所有嵌套模型。

        Args:
            model_cls: Pydantic 模型类（含泛型如 R[KbResponse]）

        Returns:
            稳定的 schema 名称，如 'R_KbResponse'
        """
        model_id = id(model_cls)

        # 去重：已注册则直接返回
        if model_id in self._model_ids:
            return self._model_ids[model_id]

        # 生成 schema 名
        schema_name = self._generate_name(model_cls)

        # 使用正确的 ref_template 生成
        generator = GenerateJsonSchema(
            ref_template="#/components/schemas/{model}"
        )
        core_schema = model_cls.__pydantic_core_schema__
        raw = generator.generate(core_schema)

        # 展平 $defs（递归处理）
        self._flatten_defs(raw)

        # 存储顶层 schema（已无 $defs）
        self._schemas[schema_name] = raw
        self._model_ids[model_id] = schema_name

        return schema_name

    def _flatten_defs(self, schema: dict[str, Any], visited: set[str] | None = None) -> None:
        """递归展平所有 $defs。

        从 schema 中提取 $defs，每个子定义单独注册，
        并递归处理子定义中可能嵌套的 $defs。
        """
        if visited is None:
            visited = set()

        defs = schema.pop("$defs", {})
        for def_name, def_schema in list(defs.items()):
            if def_name in self._schemas:
                continue
            # 递归处理子定义的 $defs
            if "$defs" in def_schema:
                self._flatten_defs(def_schema, visited)
            self._schemas[def_name] = def_schema

    def _generate_name(self, model_cls: type[BaseModel]) -> str:
        """生成稳定的可读名称。

        规则：
        - 普通模型：ClassName
        - 参数化泛型：Origin_Arg  (如 R_KbResponse)
        - 嵌套泛型：   Origin_Inner (如 PageR_KbResponse)

        避免 Pydantic 自动生成的 PageResult_KbResponse_ 样式。
        """
        origin = getattr(model_cls, "__origin__", None)

        if origin is not None:
            args = getattr(model_cls, "__args__", ())
            arg_names: list[str] = []
            for arg in args:
                if arg is type(None):
                    continue
                if hasattr(arg, "__name__"):
                    arg_names.append(arg.__name__)
                elif hasattr(arg, "__origin__"):
                    arg_names.append(self._generate_name(arg))
                else:
                    arg_names.append(str(arg))
            return origin.__name__ + "_" + "_".join(arg_names)

        return model_cls.__name__

    def as_openapi_components(self) -> dict[str, dict[str, Any]]:
        """返回 OpenAPI components/schemas 格式。"""
        return dict(self._schemas)


__all__ = ["SchemaRegistry"]
```

**关键设计决策**：

| 决策 | 选择 | 理由 |
|------|------|------|
| 去重策略 | `id(model_cls)` | 区分 `R[str]` vs `R[int]`，后者是不同的 Python 对象 |
| ref 格式 | `#/components/schemas/{model}` | 符合 OpenAPI 3.0 规范 |
| 命名策略 | `Origin_Arg` | 可读、稳定，避免 Pydantic 自动 `PageResult_KbResponse_` 样式 |
| 展平时机 | 注册时递归处理 | 一次遍历完成，避免二次遍历 |
| 泛型参数名 | `getattr(arg, '__name__', str(arg))` | 处理普通类型和嵌套泛型 |

---

### 3.2 OpenAPIParams — 参数类型映射

**职责**：将 Pydantic Field 信息（含约束、枚举、默认值）转换为 OpenAPI Parameter/Property Schema。

```python
# engine/openapi_params.py

from __future__ import annotations

import datetime
import enum
import inspect
import types
import uuid as uuid_mod
from typing import Any, get_args, get_origin

from pydantic.fields import FieldInfo


# 完整的基础类型映射
_BASE_TYPE_MAP: dict[type, tuple[str, str | None]] = {
    int: ("integer", None),
    float: ("number", "float"),
    str: ("string", None),
    bool: ("boolean", None),
    bytes: ("string", "byte"),
    datetime.datetime: ("string", "date-time"),
    datetime.date: ("string", "date"),
    datetime.time: ("string", "time"),
    uuid_mod.UUID: ("string", "uuid"),
    type(None): ("null", None),
}


def field_to_openapi_schema(
    field_info: FieldInfo | None = None,
    annotation: Any = str,
) -> dict[str, Any]:
    """将 Pydantic 字段转为 OpenAPI Schema Object。

    支持：
    - 基础类型 int/str/float/bool/datetime/UUID
    - Optional[T] / T | None → nullable
    - Literal['a', 'b'] → enum
    - Enum 类 → enum
    - list[T] → items
    - Field 约束: min_length, max_length, pattern, ge, gt, le, lt
    """
    schema: dict[str, Any] = {}
    origin = get_origin(annotation)

    # ── 提取 FieldInfo 的元数据 ──
    if field_info is not None:
        _apply_field_metadata(schema, field_info)
        _apply_field_constraints(schema, field_info)

    # ── 处理 Optional[T] / T | None ──
    if origin in (types.UnionType, _get_union_type()):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            annotation = args[0]
            schema.setdefault("nullable", True)
        elif len(args) > 1:
            return {"anyOf": [field_to_openapi_schema(None, a) for a in args]}

    # ── 基础类型映射 ──
    if annotation in _BASE_TYPE_MAP:
        type_str, fmt = _BASE_TYPE_MAP[annotation]
        schema["type"] = type_str
        if fmt:
            schema["format"] = fmt
        return schema

    # ── Literal → enum ──
    if origin is _get_literal_type():
        literal_values = [v.value if isinstance(v, enum.Enum) else v for v in get_args(annotation)]
        example = literal_values[0] if literal_values else None
        value_types = {type(v) for v in literal_values}
        if value_types <= {int}:
            schema["type"] = "integer"
        elif value_types <= {float, int}:
            schema["type"] = "number"
        elif value_types <= {bool}:
            schema["type"] = "boolean"
        else:
            schema["type"] = "string"
        schema["enum"] = literal_values
        if example is not None:
            schema.setdefault("example", example)
        return schema

    # ── Enum 类 → enum ──
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        schema["type"] = "string"
        schema["enum"] = [e.value for e in annotation]
        return schema

    # ── list[T] → array ──
    if origin is list:
        item_type = get_args(annotation)[0] if get_args(annotation) else str
        schema["type"] = "array"
        schema["items"] = field_to_openapi_schema(None, item_type)
        return schema

    # ── dict[str, T] → object ──
    if origin is dict:
        value_type = get_args(annotation)[1] if len(get_args(annotation)) >= 2 else Any
        schema["type"] = "object"
        schema["additionalProperties"] = field_to_openapi_schema(None, value_type)
        return schema

    # ── Pydantic BaseModel 子类 → $ref ──
    if isinstance(annotation, type) and issubclass(annotation, _get_basemodel_type()):
        name = annotation.__name__
        schema["$ref"] = f"#/components/schemas/{name}"
        return schema

    # ── Fallback ──
    schema.setdefault("type", "string")
    return schema


def _apply_field_metadata(schema: dict, field_info: FieldInfo) -> None:
    """从 FieldInfo 提取 metadata（description, title, default, examples, deprecated）。"""
    if field_info.description:
        schema["description"] = field_info.description
    if field_info.title:
        schema["title"] = field_info.title
    if field_info.default is not ... and field_info.default is not None:
        schema["default"] = field_info.default
    if field_info.examples:
        schema["example"] = field_info.examples[0] if isinstance(field_info.examples, list) else field_info.examples
    if field_info.deprecated:
        schema["deprecated"] = True


def _apply_field_constraints(schema: dict, field_info: FieldInfo) -> None:
    """从 FieldInfo 的 metadata 中提取约束（min_length, pattern, ge, le 等）。"""
    if not field_info.metadata:
        return

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


def field_to_openapi_parameter(
    name: str,
    field_info: FieldInfo | None,
    annotation: Any,
    location: str,
    signature_default: Any = inspect.Parameter.empty,
) -> dict[str, Any]:
    """构建 OpenAPI Parameter Object。

    Args:
        name: 参数名
        field_info: Pydantic FieldInfo（可能为 None）
        annotation: 类型注解
        location: "path" | "query" | "header" | "cookie"
        signature_default: 函数签名中的默认值

    Returns:
        OpenAPI Parameter Object
    """
    schema = field_to_openapi_schema(field_info, annotation)
    is_required = (location == "path") or (signature_default is inspect.Parameter.empty)

    param: dict[str, Any] = {
        "name": name,
        "in": location,
        "required": is_required,
        "schema": schema,
    }

    if field_info:
        if field_info.description:
            param["description"] = field_info.description
        if field_info.deprecated:
            param["deprecated"] = True
        if field_info.examples:
            param["example"] = (
                field_info.examples[0]
                if isinstance(field_info.examples, list)
                else field_info.examples
            )

    return param


# ── 兼容性辅助 ──

def _get_union_type() -> type:
    """获取 Union 类型（兼容 Python 3.9/3.10+）。"""
    import typing
    return typing.Union


def _get_literal_type() -> type:
    """获取 Literal 类型。"""
    import typing
    return typing.Literal


def _get_basemodel_type() -> type:
    """获取 BaseModel 类型。"""
    from pydantic import BaseModel
    return BaseModel


__all__ = [
    "field_to_openapi_schema",
    "field_to_openapi_parameter",
]
```

**设计决策**：

| 场景 | 处理方式 |
|------|----------|
| `str \| None` | 展开为 `str` + `nullable: true` |
| `Optional[int]` | 展开为 `int` + `nullable: true` |
| `Literal["a", "b"]` | `type: string, enum: ["a", "b"]` |
| `MyEnum` (enum.Enum) | `type: string, enum: ["val1", "val2"]` |
| `list[KbResponse]` | `type: array, items: {$ref: "...KbResponse"}` |
| `dict[str, int]` | `type: object, additionalProperties: {type: integer}` |
| `Field(ge=0, le=100)` | `minimum: 0, maximum: 100` |
| `Field(min_length=1, pattern="^[a-z]+")` | `minLength: 1, pattern: "^[a-z]+"` |

---

### 3.3 OpenAPIGenerator — 生成器

```python
# engine/openapi_v2.py

from __future__ import annotations

from typing import Any, cast

from canary_framework.common import ROUTE_ATTR, RouterMeta
from canary_framework.common.routing import parse_route_path
from canary_framework.engine.schema_registry import SchemaRegistry
from canary_framework.engine.openapi_params import field_to_openapi_parameter


class OpenAPIGenerator:
    """OpenAPI 3.0.3 文档生成器（v2）。

    相比 v1 的改进：
    - SchemaRegistry 管理模型 schema（正确 $ref）
    - 完整的 Pydantic FieldInfo → OpenAPI 映射
    - 可配置 servers、securitySchemes、tags 元数据
    """

    def __init__(
        self,
        title: str = "Canary Framework API",
        version: str = "1.0.0",
        description: str = "",
        servers: list[dict[str, str]] | None = None,
        security_schemes: dict[str, dict] | None = None,
    ) -> None:
        self.title = title
        self.version = version
        self.description = description
        self.servers = servers or [{"url": "/"}]
        self.security_schemes = security_schemes or {}
        self._registry = SchemaRegistry()

    def generate(self, router_metas: list[RouterMeta]) -> dict[str, Any]:
        """生成完整的 OpenAPI 3.0.3 文档。"""
        doc: dict[str, Any] = {
            "openapi": "3.0.3",
            "info": {"title": self.title, "version": self.version},
            "servers": self.servers,
            "paths": {},
            "components": {"schemas": {}},
        }

        if self.description:
            doc["info"]["description"] = self.description

        if self.security_schemes:
            doc["components"]["securitySchemes"] = self.security_schemes

        for meta in router_metas:
            self._add_router_paths(cast("dict[str, Any]", doc["paths"]), meta)

        doc["components"]["schemas"] = self._registry.as_openapi_components()

        return doc

    def _add_router_paths(
        self, paths: dict[str, Any], meta: RouterMeta
    ) -> None:
        """将单个 router 的所有路由添加到 paths。"""
        for route_fn in meta.routes:
            raw_info = cast("dict[str, Any]", getattr(route_fn, ROUTE_ATTR, {}))
            if not raw_info:
                continue

            method = cast(str, raw_info.get("method", "get")).lower()
            path = cast(str, raw_info.get("path", "/"))

            # 构建完整路径
            starlette_path, path_params, query_params = parse_route_path(path)
            full_path = (meta.prefix or "") + starlette_path

            # 构建操作
            operation = self._build_operation(raw_info, meta, route_fn)

            paths.setdefault(full_path, {})[method] = operation

    def _build_operation(
        self, info: dict[str, Any], meta: RouterMeta, route_fn: Any
    ) -> dict[str, Any]:
        """构建单个 Operation Object。"""
        import inspect

        op: dict[str, Any] = {}

        # 基本信息
        for key, src in [
            ("summary", "summary"),
            ("description", "description"),
            ("operationId", "operation_id"),
        ]:
            if info.get(src):
                op[key] = info[src]
        if info.get("deprecated"):
            op["deprecated"] = True

        # Tags
        router_tags = meta.tags or []
        route_tags = cast("list[str]", info.get("tags") or [])
        merged_tags = list(dict.fromkeys(router_tags + route_tags))
        if merged_tags:
            op["tags"] = merged_tags

        # Parameters
        params = self._build_parameters(info, route_fn)
        if params:
            op["parameters"] = params

        # Request body
        request_model = info.get("request_model")
        if request_model is not None:
            op["requestBody"] = self._build_request_body(request_model)

        # Responses
        op["responses"] = self._build_responses(info)

        return op

    def _build_parameters(
        self, info: dict[str, Any], route_fn: Any
    ) -> list[dict[str, Any]]:
        """构建参数列表（path + query）。"""
        import inspect

        params: list[dict[str, Any]] = []
        path = cast(str, info.get("path", "/"))
        _, path_names, query_names = parse_route_path(path)
        sig = inspect.signature(route_fn)

        for name in path_names:
            param = sig.parameters.get(name)
            annotation = param.annotation if param and param.annotation is not inspect.Parameter.empty else str
            p = field_to_openapi_parameter(name, None, annotation, "path")
            p["required"] = True
            params.append(p)

        for name in query_names:
            param = sig.parameters.get(name)
            annotation = param.annotation if param and param.annotation is not inspect.Parameter.empty else str
            default = param.default if param else inspect.Parameter.empty
            p = field_to_openapi_parameter(name, None, annotation, "query", default)
            params.append(p)

        return params

    def _build_request_body(self, model_cls: type) -> dict[str, Any]:
        """构建 Request Body Object。"""
        from pydantic import BaseModel

        schema_name = self._registry.register(model_cls)
        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                }
            },
        }

    def _build_responses(self, info: dict[str, Any]) -> dict[str, Any]:
        """构建 Responses Object。"""
        responses: dict[str, Any] = {}

        # 用户定义的响应
        user_responses = cast("dict[str, Any]", info.get("responses") or {})
        for status_code, resp_def in user_responses.items():
            status_str = str(status_code)
            if isinstance(resp_def, dict) and "model" in resp_def:
                model_cls = resp_def["model"]
                schema_name = self._registry.register(model_cls)
                responses[status_str] = {
                    "description": resp_def.get(
                        "description",
                        "Successful Response" if status_code == 200 else "Error Response",
                    ),
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    },
                }
            else:
                responses[status_str] = resp_def

        # 默认响应模型
        response_model = info.get("response_model")
        if response_model is not None and "200" not in responses:
            schema_name = self._registry.register(response_model)
            responses["200"] = {
                "description": "Successful Response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                    }
                },
            }

        return responses


__all__ = ["OpenAPIGenerator"]
```

---

### 3.4 路由 URL 修复

**Problem**: Mount 用服务名 `/KBRouterRouter` 当路径前缀，Router 内部又加 `/kb` 前缀，导致 `/KBRouterRouter/kb/` 而非用户期望的 `/kb/`。

**Fix**:

```python
# core/module.py — ModuleBase.asgi_app 属性

# BEFORE (第 219-225 行):
for name in self._cf_startup_order:
    entry = registry.get_by_name(name)
    inst = entry.instance
    asgi = getattr(inst, "asgi_app", None)
    if asgi is not None:
        app = cast(ASGIApp, asgi)
        routes.append(Mount(f"/{name}", app=app))

# AFTER:
for name in self._cf_startup_order:
    entry = registry.get_by_name(name)
    inst = entry.instance
    asgi = getattr(inst, "asgi_app", None)
    if asgi is not None and is_cf_router(entry.cls):
        meta = get_router_meta(entry.cls)
        mount_path = meta.prefix if meta and meta.prefix else f"/{name}"
        routes.append(Mount(mount_path, app=asgi))
```

```python
# core/router.py — RouterBase._route_handler

# DELETE 第 168-171 行:
# router_meta = get_router_meta(cls)
# if router_meta and router_meta.prefix:
#     starlette_path = router_meta.prefix + starlette_path
```

**结果**：

| Before | After |
|--------|-------|
| `/KBRouterRouter/kb/` | `/kb/` |
| `/FileRouterRouter/file/` | `/file/` |
| `/CollRouterRouter/coll/` | `/coll/` |

---

## API 设计

### 模块级配置

```python
# app/main.py

from canary_framework import module

@module(
    services=[KBRouter, FileRouter],
    docs={
        "openapi_url": "/api/v1/openapi.json",
        "docs_url": "/api/v1/docs",
        "redoc_url": "/api/v1/redoc",
        "swagger_ui_js": "/static/swagger-ui-bundle.js",  # None = 用 CDN
        "redoc_js": "/static/redoc.standalone.js",
    },
    servers=[
        {"url": "https://api.example.com", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Local"},
    ],
    security_schemes={
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    },
)
class AppModule:
    pass
```

### 路由级配置（不变）

```python
@router(prefix="/kb", tags=["kb"])
class KBRouter:
    kb_service: KbService

    @post(
        path="/",
        summary="创建知识库",
        description="传入必要参数，为当前用户创建知识库",
        request_model=CreateKbRequest,
        response_model=R[KbResponse],
        responses={
            "200": {"model": R[KbResponse], "description": "创建成功"},
            "400": {"model": R[str]},
        },
        tags=["admin"],
        deprecated=False,
        operation_id="createKnowledgeBase",
    )
    def create(self, request: CreateKbRequest):
        ...
```

### 参数级支持（新增）

```python
from pydantic import Field

# Query 参数支持 Field 注解
@get(path="/list")
def list(
    self,
    page: int = Field(default=1, ge=1, description="页码"),
    size: int = Field(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Field(default=None, min_length=1, description="搜索关键词"),
    status: Literal["active", "archived"] = "active",
):
    ...
```

---

## 与现有实现的对比

| 维度 | 当前实现 (v0.4.10) | 重构方案 |
|------|-------------------|----------|
| **$ref 处理** | ❌ 使用 `#/$defs/X`，在 OpenAPI 中无效 | ✅ `ref_template` + 展平 `$defs` |
| **泛型模型** | ❌ 嵌套子模型引用悬空 | ✅ 递归注册，正确引用 |
| **Schema 去重** | ❌ `__name__` 去重，泛型冲突 | ✅ `id(model)` 去重 |
| **URL 路由** | ❌ Mount + Router 双重前缀 | ✅ 单层前缀（router prefix 做 mount） |
| **类型映射** | ❌ 仅 int/str/bool/float 4 种 | ✅ 15+ 种类型 + format |
| **枚举** | ❌ 不识别 | ✅ Literal + Enum 自动生成 enum 数组 |
| **Field 约束** | ❌ 忽略 | ✅ minLength, pattern, ge, le, ... |
| **datetime/UUID** | ❌ 显示为 `string` | ✅ `format: date-time` / `uuid` |
| **servers 块** | ❌ 无 | ✅ 可配置 |
| **securitySchemes** | ❌ 无 | ✅ 可配置 |
| **CDN 配置** | ❌ 硬编码 | ✅ 可配置，支持本地化 |
| **openapi.json 路径** | ❌ 固定 `/openapi.json` | ✅ 可配置子路径 |
| **代码行数** | ~220 行 | ~350 行（拆分为 3 个文件） |

---

## 迁移指南

对于 `canary_framework` 的使用者（如本项目的 `app/`），**无需修改任何代码**。

`@router`、`@post`、`@get` 等装饰器 API 完全向后兼容：

```python
# ✅ 这些写法全部不变
@router(prefix="/kb", tags=["kb"])
class KBRouter:
    @post(path="/", response_model=R[KbResponse])
    def create(self, request: CreateKbRequest): ...
    
    @get(path="/", response_model=PageR[KbResponse])
    def list(self, page: int = 1, size: int = 20): ...
```

唯一的 breaking change 是 URL 从 `/KBRouterRouter/kb/` 变为 `/kb/`，但这是**修复 bug** 而非破坏兼容性——它使 URL 与 `@router(prefix="/kb")` 声明保持一致。
