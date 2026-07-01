# 变更日志 / Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)与下述[版本策略](#版本策略--versioning-policy)。

> 早期各补丁版本（`0.1.x`–`0.4.x`）的完整细节以 git tag 与提交历史为准，
> 这里只保留有意义的里程碑。

## [Unreleased] — 0.5.2

### Router 重设计 / Router redesign

- **单点记忆化组装**：service 与 module 统一通过 `_cf_collect_routes()` 交出「已绑 self、
  已拼前缀」的 `ResolvedRoute` 贡献；被运行的节点（service 或 module）用同一个 `_cf_assemble()`
  一次性组装出**一张 Starlette 路由表 + 一份 OpenAPI + 文档端点**。删除了分散在四处的旧聚合
  逻辑（`_collect_routes` / `_route_handler` / `_cf_get_root_routes` / `_cf_collect_route_infos`
  / `_cf_generate_openapi` / `get_mount_path`）与 standalone/mounted 分支。`src/` 净减约 60 行。
- 新增 `ServiceBase.openapi()`：随时按需（记忆化）导出 OpenAPI 文档。

### 修复 / Fixed

- **OpenAPI schema 缓存泄漏**：schema 注册表改为「每次生成」的局部变量，同一进程内重复生成不再
  产生悬空 `$ref`。
- **path 参数 + 请求体**：请求处理全程按**参数名**绑定 kwargs，`PUT /x/{id}` 带 body 不再 500。
- **缺失必填 query 参数**：返回 **422**（此前 500）。
- **bool query 参数**：`1/true/yes/on`（大小写无关）→ `True`，无法识别 → 422（此前只认 `true`）。
- **元组返回**：`(body, status_code)` 正确设置状态码（此前被字符串化为 200）。

### 变更 / Changed（⚠️ 行为变更 / behavior change）

- **显式前缀（D4）**：去除「无 prefix 时自动挂到 `/{ServiceName}`」的隐式命名空间。路由一律使用
  显式 `Router(prefix=...)`；路径冲突在组装时报 `ValueError`。迁移：依赖 `/{name}` 的服务请补上
  显式 `prefix`。

## [0.5.1] — 2026-06-15

- 显式声明 `pydantic-settings` 依赖（`BaseSettings` / 配置类）。

## [0.5.0] — 2026-06-15

- 配置系统与核心优化；router 重构。

## [0.4.11] — 2026-06-05

- 底层优化：要求通过类型注解继承基类；修复 router 相关缺陷；推出独立配置类。

## [0.4.0] — 2026-05-31

- **ASGI 集成、移除独立 web 包的大重构**：框架从 FastAPI 迁移到直接的 ASGI（Starlette）集成，
  重新设计模块启动生命周期。`0.4.x` 后续版本持续打磨依赖注入体验与日志能力。

## [0.3.0] — 2026-05-27

- 移除 Context 系统，改为基于类型注解的依赖注入；统一以 config 承载生命周期配置。

## [0.2.0] — 2026-05-25

- 发布流程与分支规范调整。

## [0.1.0] — 2026-05-25

- 首个开源版本：README、文档、社区文件与 CI/CD。

---

## 版本策略 / Versioning Policy

只要**核心设计理念不变**——service 为最小单元；module 组合 service 且 module *即* service；
基于类型注解的依赖注入；装饰器式 API——我们就留在 **0.5.x** 线上积极维护与迭代：新特性与修复
以 `0.5.x` 发布，**单纯的内部重构或行为收敛不会抬升版本线**。只有底层设计理念发生根本改变时，
版本线才会前进。

As long as the **core design philosophy is unchanged** — service is the smallest unit; a module
composes services and *is* a service; DI via type annotations; a decorator-driven API — we stay on
the **0.5.x** line: features and fixes ship as `0.5.x`, and internal refactors or behavior tightening
alone do not advance the version line. It advances only when the fundamental design changes.
