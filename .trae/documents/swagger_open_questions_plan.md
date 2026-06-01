# Swagger/OpenAPI 集成功能 - 遗留问题完善计划

## Repo Research 结论

当前 Swagger/OpenAPI 集成功能的**核心功能**已经实现：
- ✅ HTTP 方法装饰器支持 OpenAPI 参数（summary、description、response_model、tags、deprecated）
- ✅ OpenAPI Schema 生成器
- ✅ Swagger UI 和 ReDoc 端点
- ✅ ModuleBase 自动挂载文档路由

但是需求文档中的两个 Open Questions 尚未实现：
1. 请求体模型的自动解析
2. 路径参数和查询参数的自动提取

## 需要编辑的文件和模块

### 1. 增强 HTTP 方法装饰器 (`decorators/router.py`)
- 添加 `request_model` 参数
- 添加 `path_params` 和 `query_params` 参数定义
- 增强 `ROUTE_ATTR` 存储结构

### 2. 增强 OpenAPI Schema 生成器 (`engine/openapi.py`)
- 解析 Pydantic 请求模型并添加到 OpenAPI 请求体定义
- 自动从路由路径提取路径参数
- 支持定义查询参数

### 3. 核心路由处理 (`core/router.py`)
- 添加请求模型自动解析功能
- 提供查询参数和路径参数的类型转换

### 4. 文档更新 (`docs/zh/web.md`, `docs/en/web.md`)
- 更新 OpenAPI 文档章节，添加新功能说明
- 添加完整的使用示例

## 修改步骤

### 步骤 1: 增强 HTTP 装饰器

在 `decorators/router.py` 中：
- 在 `_http_method` 函数添加 `request_model`、`path_params`、`query_params` 等参数
- 更新所有 HTTP 装饰器（get/post/put/delete/patch）以传递新参数
- 更新 `ROUTE_ATTR` 存储结构

### 步骤 2: 增强 Schema 生成器

在 `engine/openapi.py` 中：
- 添加请求体模型转换逻辑（requestBody）
- 添加路径参数和查询参数的 OpenAPI 定义生成
- 更新 `generate_openapi_schema` 函数

### 步骤 3: 更新核心路由处理

在 `core/router.py` 中：
- 增强 `_auto_response` 函数，添加请求模型解析
- 提供参数转换辅助函数

### 步骤 4: 更新文档

在中文和英文文档中：
- 添加新参数的说明
- 添加完整的使用示例
- 更新表格

### 步骤 5: 添加测试用例

在 `tests/unit/test_openapi.py` 中：
- 添加请求模型测试
- 添加路径和查询参数测试

## 潜在的依赖项和注意事项

1. 依赖 Pydantic v1 或 v2 - 代码已经有兼容逻辑
2. 向后兼容性 - 现有装饰器调用保持不变，新增参数是可选的
3. 类型注解 - 需要确保与 pyright 和 mypy 兼容
4. Starlette 依赖 - 利用 Starlette 已有的 Request 对象功能

## 风险处理

| 风险 | 描述 | 处理策略 |
|------|------|----------|
| Pydantic 版本兼容性 | 同时有 v1 和 v2 用户 | 保持已有的版本检测逻辑 |
| 向后不兼容 | 可能破坏现有代码 | 确保新增参数都是可选的，默认 None |
| 类型检查错误 | 类型注解可能导致 lint 错误 | 使用 TYPE_CHECKING 条件导入 |

## 预期结果

实现完成后，用户可以：
1. 使用 `request_model` 参数自动解析和验证请求体
2. 使用 `path_params` 和 `query_params` 定义参数类型和文档
3. 在 Swagger UI 中看到完整的请求和响应文档
4. 获得自动的请求体和参数验证
