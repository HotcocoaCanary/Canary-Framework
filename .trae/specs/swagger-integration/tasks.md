# Canary Framework - Swagger/OpenAPI 集成功能 - 实现计划

## [ ] Task 1: 更新 HTTP 方法装饰器支持 OpenAPI 参数
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 扩展 `_http_method` 函数，支持 summary、description、response、response_model、tags、deprecated 等参数
  - 更新 get/post/put/delete/patch 装饰器以传递这些参数
  - 更新 ROUTE_ATTR 存储结构，包含完整的 OpenAPI 元数据
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic` TR-1.1: 装饰器正确存储 OpenAPI 参数到函数属性
  - `programmatic` TR-1.2: 响应模型信息正确保存
- **Notes**: 需要定义新的路由元数据结构

## [ ] Task 2: 创建 OpenAPI Schema 生成器
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 创建 `openapi.py` 模块，包含 OpenAPI Schema 生成逻辑
  - 实现从路由元数据提取并生成 OpenAPI 3.0 Schema
  - 支持从 Pydantic 模型自动提取 JSON Schema
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-2.1: 正确生成 OpenAPI 3.0 格式的 JSON
  - `programmatic` TR-2.2: Pydantic 模型正确转换为 JSON Schema
- **Notes**: 需要遍历所有 RouterMeta 收集路由信息

## [ ] Task 3: 集成 Swagger UI 和 ReDoc
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 安装并集成 `swagger-ui-py` 或使用 Starlette 静态文件服务
  - 创建 `/docs` 端点提供 Swagger UI
  - 创建 `/redoc` 端点提供 ReDoc UI
  - 创建 `/openapi.json` 端点提供原始 Schema
- **Acceptance Criteria Addressed**: AC-3, AC-4
- **Test Requirements**:
  - `human-judgment` TR-3.1: `/docs` 页面可访问并显示 API 列表
  - `human-judgment` TR-3.2: `/redoc` 页面可访问
  - `programmatic` TR-3.3: `/openapi.json` 返回有效的 JSON Schema
- **Notes**: 需要处理静态文件服务

## [ ] Task 4: 更新 ModuleBase 自动挂载文档路由
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 修改 `ModuleBase.asgi_app` 属性，自动挂载文档路由
  - 确保文档路由在所有子服务路由之后挂载
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic` TR-4.1: 模块的 ASGI 应用包含 `/docs` 和 `/openapi.json` 路由
- **Notes**: 需要确保懒加载时自动添加文档路由

## [ ] Task 5: 更新 RouterMeta 支持路由级别的 tags
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 确保路由级别的 tags 与 router 级别的 tags 正确合并
  - 支持路由级别的 OpenAPI 元数据覆盖 router 级别的配置
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-5.1: 路由级 tags 正确合并到 router tags
- **Notes**: 需要处理 tags 的合并逻辑

## [ ] Task 6: 添加测试用例
- **Priority**: P1
- **Depends On**: All
- **Description**: 
  - 为 OpenAPI Schema 生成器编写单元测试
  - 为 HTTP 装饰器参数编写单元测试
- **Acceptance Criteria Addressed**: All
- **Test Requirements**:
  - `programmatic` TR-6.1: 所有单元测试通过
- **Notes**: 使用 pytest 编写测试

## [x] Task 7: 更新文档
- **Priority**: P2
- **Depends On**: All
- **Description**: 
  - 更新 API 参考文档，添加 OpenAPI 参数说明
  - 添加 Swagger UI 使用指南
- **Acceptance Criteria Addressed**: AC-1, AC-3
- **Test Requirements**:
  - `human-judgment` TR-7.1: 文档清晰说明新功能
- **Notes**: 更新 docs/zh/web.md 和 docs/en/web.md