# Canary Framework OpenAPI / Swagger Bug Report

> **版本**: `canary_framework==0.4.10`
> **日期**: 2026-06-04
> **严重程度**: Critical — 泛型响应模型无法在 Swagger UI 中渲染；路由 404

---

## 目录

1. [Bug #1: OpenAPI `$ref` 解析失败 — Swagger UI 报错](#bug-1-openapi-ref-解析失败--swagger-ui-报错)
2. [Bug #2: 路由 URL 双重前缀 — POST /kb/ 返回 404](#bug-2-路由-url-双重前缀--post-kb-返回-404)
3. [Bug #3: Schema 命名冲突](#bug-3-schema-命名冲突)
4. [缺陷清单 (共 14 项)](#缺陷清单)

---

## Bug #1: OpenAPI `$ref` 解析失败 — Swagger UI 报错

### 现象

1. 访问 `/docs` 可以看到 Swagger UI 页面
2. 展开任意使用泛型响应模型的接口时报错：

```
Resolver error at paths./kb/.post.responses.200.content.application/json.schema.properties.data.anyOf.0.$ref
Could not resolve reference: Could not resolve pointer: /$defs/KbResponse does not exist in document
```

### 复现步骤

```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class R(BaseModel, Generic[T]):
    """统一响应封装"""
    code: int = Field(default=0)
    data: Optional[T] = Field(default=None)
    msg: str = Field(default="ok")

class KbResponse(BaseModel):
    id: str
    name: str

# 路由定义
from canary_framework import router, post

@router(prefix="/kb", tags=["kb"])
class KBRouter:
    @post(
        path="/",
        response_model=R[KbResponse],
        responses={"200": {"model": R[KbResponse]}},
    )
    def create(self, request: CreateKbRequest):
        ...
```

### 根因分析

**出错位置**: `canary_framework/engine/openapi.py` 第 159、179、198 行

框架调用 `model_cls.model_json_schema()` 生成 JSON Schema 后，**直接将原始 schema 整体存入 `components/schemas/` 中**，未处理 Pydantic v2 生成的内部 `$defs` 引用。

Pydantic v2 对泛型模型 `R[KbResponse]` 生成的 JSON Schema：

```json
{
  "$defs": {
    "KbResponse": {
      "properties": {
        "id": { "title": "Id", "type": "string" },
        "name": { "title": "Name", "type": "string" }
      },
      "required": ["id", "name"],
      "type": "object"
    }
  },
  "properties": {
    "code": { "default": 0, "type": "integer" },
    "data": {
      "anyOf": [
        { "$ref": "#/$defs/KbResponse" },   // ← 问题在这里
        { "type": "null" }
      ],
      "default": null
    },
    "msg": { "default": "ok", "type": "string" }
  }
}
```

**问题链路**：

```
model_json_schema() 输出
  │
  ├─ $defs.KbResponse 的子定义
  └─ $ref: "#/$defs/KbResponse"    ← JSON Schema 文档内部的相对引用
         │
         ▼ 存入 OpenAPI
  components/schemas/R[KbResponse] = { ... $ref: "#/$defs/KbResponse" ... }
         │
         ▼ Swagger UI 尝试解析
  在 OpenAPI 文档根上寻找 /$defs/KbResponse
  → OpenAPI 3.0 使用 components/schemas，不使用 $defs
  → 解析失败 ❌
```

**验证**：

```python
>>> from app.common.response import R
>>> from app.module.kb.schema import KbResponse
>>> schema = R[KbResponse].model_json_schema()
>>> schema["properties"]["data"]["anyOf"][0]["$ref"]
'#/$defs/KbResponse'    # ← 这个路径在 OpenAPI 文档中不存在
```

### 修复方向

1. **使用 `ref_template` 参数**：`model_json_schema(ref_template='#/components/schemas/{model}')` 将 `$ref` 从 `#/$defs/X` 改为 `#/components/schemas/X`

2. **展平 `$defs`**：递归提取所有 `$defs` 中的子模型定义，每个单独注册到 `components/schemas/` 中，并从顶层 schema 移除 `$defs` 键

3. **Schema 去重**：按模型 `id()` 去重而非 `__name__`，避免 `R[str]` 和 `R[int]` 命名冲突

### 修复代码示例（最小改动）

```python
# openapi.py 中所有 model_json_schema() 调用改为:
def _register_model_schema(
    model_cls: type[BaseModel],
    schemas_dict: dict,
    added: set[int],
) -> str:
    """注册模型 schema 并展平 $defs。返回 schema 引用名。"""
    model_id = id(model_cls)
    model_name = model_cls.__name__

    # 生成带正确 ref 模板的 schema
    raw = model_cls.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )

    # 展平 $defs
    if "$defs" in raw:
        for def_name, def_schema in raw.pop("$defs").items():
            if def_name not in schemas_dict:
                schemas_dict[def_name] = def_schema
        # 递归处理子定义的 $defs
        for def_name, def_schema in list(schemas_dict.items()):
            if "$defs" in def_schema:
                for sub_name, sub_schema in def_schema.pop("$defs").items():
                    if sub_name not in schemas_dict:
                        schemas_dict[sub_name] = sub_schema

    if model_id not in added:
        schemas_dict[model_name] = raw
        added.add(model_id)

    return model_name
```

---

## Bug #2: 路由 URL 双重前缀 — POST /kb/ 返回 404

### 现象

```bash
$ curl -X POST http://localhost:8000/kb/ -d '{"name":"test"}'
# → 404 Not Found

# 日志:
# INFO: 127.0.0.1:55460 - "POST /kb/ HTTP/1.1" 404 Not Found
```

实际可用的 URL：`POST /KBRouterRouter/kb/`（非预期）

### 根因分析

路由 URL 被**两层前缀叠加**：

| 层级 | 前缀 | 来源 |
|------|------|------|
| Module Mount | `/KBRouterRouter` | `ModuleBase.asgi_app` 第 225 行: `Mount(f"/{name}", ...)` |
| Router 路径 | `/kb` | `RouterBase._route_handler` 第 171 行: `prefix + starlette_path` |
| 路由路径 | `/` | 装饰器 `@post(path="/")` |
| **最终 URL** | **`/KBRouterRouter/kb/`** | 双重前缀 |

**核心问题**：

1. `ModuleBase.asgi_app` 用服务注册名 `name`（即 `KBRouterRouter`）作为 Mount 路径
2. `RouterBase._route_handler` 再次应用 `router_meta.prefix`（即 `/kb`）
3. 两处代码彼此不知道对方会加前缀

**服务名生成逻辑** — `decorators/router.py` 第 306 行：

```python
name = cls.__name__ + "Router"
# KBRouter → "KBRouterRouter"  （Router 后缀叠加）
```

这个实现细节泄露到了公开 URL 中。

### 修复方向

**方案 A**（推荐）：Mount 使用 router 的 `prefix`，移除 `_route_handler` 中的二次前缀应用

```python
# module.py — asgi_app 属性中:
for name in self._cf_startup_order:
    entry = registry.get_by_name(name)
    inst = entry.instance
    asgi = getattr(inst, "asgi_app", None)
    if asgi is not None and is_cf_router(entry.cls):
        meta = get_router_meta(entry.cls)
        mount_path = meta.prefix if meta and meta.prefix else f"/{name}"
        routes.append(Mount(mount_path, app=asgi))

# router.py — _route_handler 中删除:
# if router_meta and router_meta.prefix:
#     starlette_path = router_meta.prefix + starlette_path
```

**方案 B**：在 `@router` 装饰器中允许显式指定 mount 名称

```python
@router(prefix="/kb", name="kb", tags=["kb"])
class KBRouter:
    ...
```

---

## Bug #3: Schema 命名冲突

### 现象

两个不同接口使用 `R[str]` 和 `R[int]` 作为响应模型时，`model_cls.__name__` 都是 `"R"`，后注册的 schema 会覆盖前一个。

### 根因

`openapi.py` 第 160/180/198 行使用 `model_cls.__name__` 去重，但泛型类型 `R[str]` 和 `R[int]` 的 `__name__` 相同。

### 修复

改用 `id(model_cls)` 去重。

---

## 缺陷清单

以下是在完整代码审查中发现的全部问题（共 14 项）：

| # | 类别 | 问题 | 位置 | 影响 |
|---|------|------|------|------|
| 1 | Critical | `$ref` 使用 `#/$defs/X`，在 OpenAPI 3.0 中无法解析 | `openapi.py:159/179/198` | Swagger UI 报错，所有泛型模型不可用 |
| 2 | Major | Mount 路径与 router prefix 双重叠加 | `module.py:225` + `router.py:171` | 用户预期的 URL 返回 404 |
| 3 | Major | Schema 用 `__name__` 去重，泛型模型命名冲突 | `openapi.py:160/180/198` | 同名字段显示错误 schema |
| 4 | Major | `$defs` 从未被展平提取 | `openapi.py:159-163` | 子模型引用悬空 |
| 5 | Medium | `Optional[T]` / `T \| None` 参数类型未正确处理 | `openapi.py:120-152` | schema 可能出错 |
| 6 | Medium | Pydantic Field 约束（`min_length`、`pattern`、`ge`、`description`）未提取 | `openapi.py:120-152` | 文档缺少约束信息 |
| 7 | Medium | `enum` / `Literal` 类型未检测 | `openapi.py:120-152` | 枚举值未在文档中显示 |
| 8 | Low | `datetime`/`date`/`uuid` 缺少 `format` 字段 | `openapi.py:18-23` | 工具无法自动格式化 |
| 9 | Low | Query 参数 `required` 硬编码为 `False` | `openapi.py:149` | 无默认值的必填参数显示为可选 |
| 10 | Low | `requestBody` 无 `description` | `openapi.py:164-170` | 请求体无说明 |
| 11 | Low | 无 `servers` 块 | `openapi.py:60-68` | "Try it out" 使用 localhost 而非实际地址 |
| 12 | Low | 无 `securitySchemes` 支持 | `openapi.py` 整体 | 无法在文档中描述认证方式 |
| 13 | Low | Swagger UI / ReDoc CDN 硬编码 | `module.py:42-68` | 离线/内网环境不可用 |
| 14 | Low | `/openapi.json` 路由硬编码在模块根 | `module.py:247-249` | 无法挂载到 `/api/v1/openapi.json` |

---

## 总结

当前 `openapi.py` 的实现是一个快速原型级别。核心缺陷在于：将 Pydantic 的 `model_json_schema()` 输出**当作黑盒直接嵌入 OpenAPI 文档**，没有处理 JSON Schema 和 OpenAPI 3.0 之间的差异（`$defs` vs `components/schemas`、`$ref` 路径格式等）。

建议完整重写 `engine/openapi.py`，新增 `SchemaRegistry` 模块负责 schema 管理，并调整 `module.py` 中的路由挂载逻辑。
