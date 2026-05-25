# 变更日志

## [0.1.0] - 2026-05-25

### 新增
- 核心引擎 `Canary`：服务生命周期编排（init → start → stop）
- 装饰器 `@service` / `@module`：声明服务和模块
- 装饰器 `@config`：基于 pydantic-settings 的自动配置加载
- 装饰器 `@on_init` / `@on_start` / `@on_end`：生命周期钩子
- 依赖注入：按 snake_case 自动注入依赖实例
- 拓扑排序启动：基于 Kahn 算法保证依赖顺序
- Context 上下文系统：parent 链向上委托配置和依赖解析
- Web 集成 `WebCanary`：自动接入 FastAPI + Uvicorn
- 装饰器 `@web` / `@router` / `@get` / `@post` / `@put` / `@delete` / `@patch`
- 配置前缀分发：`uvicorn_*` → uvicorn，`fastapi_*` → FastAPI
- 框架日志系统：`CF_LOG_LEVEL` 环境变量控制，与 uvicorn 隔离
