# Canary Framework - Swagger/OpenAPI 集成功能 - 产品需求文档

## Overview
- **Summary**: 为 Canary Framework 添加 Swagger/OpenAPI 自动集成功能，允许用户通过装饰器参数定义 API 文档元数据，并自动生成 OpenAPI Schema 并提供 Swagger UI 访问。
- **Purpose**: 提供类似 FastAPI 的自动 API 文档生成功能，减少手动编写文档的工作量，提高 API 开发效率。
- **Target Users**: 使用 Canary Framework 开发 Web API 的开发者。

## Goals
- 增强 HTTP 方法装饰器（get/post/put/delete/patch），支持定义 request、response、summary、description 等 OpenAPI 参数
- 自动收集所有路由的 OpenAPI 元数据
- 生成符合 OpenAPI 3.0 规范的 JSON Schema
- 提供 Swagger UI 界面访问（默认路径 `/docs` 和 `/redoc`）
- 支持通过 `@router` 的 `tags` 参数进行 API 分组

## Non-Goals (Out of Scope)
- 不支持 OpenAPI 3.1 或其他版本
- 不支持 OAuth2 安全定义的自动生成（需手动配置）
- 不支持自定义 Swagger UI 主题或样式

## Background & Context
- 当前框架使用 Starlette 作为底层 HTTP 框架
- 路由装饰器已支持基本的路径和 HTTP 方法定义
- 需要集成 `swagger-ui-py` 或类似库提供 UI 界面

## Functional Requirements
- **FR-1**: HTTP 方法装饰器支持 OpenAPI 参数（summary、description、response、tags、deprecated）
- **FR-2**: 自动收集所有路由的 OpenAPI 元数据
- **FR-3**: 生成标准 OpenAPI 3.0 JSON Schema
- **FR-4**: 提供 Swagger UI 端点（`/docs`）
- **FR-5**: 提供 ReDoc 端点（`/redoc`）
- **FR-6**: ModuleBase 自动挂载 Swagger UI 路由

## Non-Functional Requirements
- **NFR-1**: 零配置启用，默认自动集成
- **NFR-2**: 性能影响最小化，仅在访问文档时生成 Schema
- **NFR-3**: 向后兼容，现有代码无需修改即可使用

## Constraints
- **Technical**: 依赖 `swagger-ui-py` 和 `pydantic` 库
- **Dependencies**: Starlette 路由系统

## Assumptions
- 用户了解基本的 OpenAPI 概念
- 用户可能使用 Pydantic 模型定义请求/响应结构

## Acceptance Criteria

### AC-1: HTTP 方法装饰器支持 OpenAPI 参数
- **Given**: 用户使用 `@get("/path", summary="获取资源", description="获取单个资源详情")` 定义路由
- **When**: 应用启动后访问 `/docs`
- **Then**: Swagger UI 显示该路由的 summary 和 description
- **Verification**: `programmatic`

### AC-2: 支持响应模型定义
- **Given**: 用户使用 `@get("/path", response=200, response_model=UserModel)` 定义路由
- **When**: 生成 OpenAPI Schema
- **Then**: Schema 包含正确的响应定义和模型结构
- **Verification**: `programmatic`

### AC-3: Swagger UI 可访问
- **Given**: 应用启动
- **When**: 访问 `http://localhost:8000/docs`
- **Then**: 显示 Swagger UI 界面，列出所有 API 端点
- **Verification**: `human-judgment`

### AC-4: ReDoc UI 可访问
- **Given**: 应用启动
- **When**: 访问 `http://localhost:8000/redoc`
- **Then**: 显示 ReDoc 文档界面
- **Verification**: `human-judgment`

### AC-5: 自动路由分组
- **Given**: 多个路由使用相同的 `tags`
- **When**: 访问 Swagger UI
- **Then**: 路由按 tags 分组显示
- **Verification**: `human-judgment`

## Open Questions
- [ ] 是否需要支持请求体模型的自动解析？
- [ ] 是否支持路径参数和查询参数的自动提取？