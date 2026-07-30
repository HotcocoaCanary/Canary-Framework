# 0.6.0 新特性

0.6.0 是无兼容层的破坏性重设计，Service、Router、Module 成为不同的显式层次。

## 迁移表

| 0.5.x | 0.6.0 |
|---|---|
| `@service(config=...)` | `@service()`；配置放到运行根 Router 或 Module |
| `router = Router(prefix=...)` | `@router(prefix=...) class X(RouterBase)` |
| `@router.get(...)` | 顶层 `@get(...)` |
| `@module(services=[...])` | `@module(children=(...))` |
| Module 自有端点 | 显式 Router 子节点 |
| 同步 `app.init()` | `await app.init()` |
| `@before_startup/@before_shutdown` | async `on_startup/on_shutdown` |
| services 中的配置类 | 传给 Router/Module 装饰器的配置类 |
| 任意 Service 都是 ASGI | 只有运行根 Router/Module 是 ASGI |
| 初始化前空 OpenAPI | `ApplicationNotInitializedError` |

## 亮点

- Router 成为最小可运行应用。
- Module 组合显式且具有作用域。
- 异步初始化与 ASGI lifespan 分离。
- 路由、OpenAPI、ASGI 共用一条经过校验的编译流水线。
- 根配置独占 OpenAPI 元数据，避免嵌套泄漏。
- 严格方向与作用域规则让依赖实例身份可预测。

请继续阅读[快速开始](quickstart.md)与迁移后的可运行示例。
