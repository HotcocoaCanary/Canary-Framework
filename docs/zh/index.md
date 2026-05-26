# CF (Canary Framework)

轻量级声明式 Python 服务框架。

**核心理念：服务是最小单元。模块组合服务。模块本身也是服务。**

## 包

| 包 | 用途 |
|----|------|
| [Core](./core.md) | `@service`、`@module`、`@config`、生命周期、DI |
| [Web / FastAPI](./fastapi.md) | `@router`、`@get`/`@post`、`WebCanary` — HTTP 服务器 |

## 目录

- [快速开始](./quickstart.md)
- **Core 包**
    - [概览](./core.md)
    - [服务](./services.md)
    - [模块](./modules.md)
    - [配置](./configuration.md)
    - [生命周期](./lifecycle.md)
    - [依赖注入](./dependency-injection.md)

- **Web 包**
    - [概览](./web.md)
    - [FastAPI 集成](./fastapi.md)
- [API 参考](./api-reference.md)
