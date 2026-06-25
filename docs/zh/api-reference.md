# API 参考 (API Reference)

这是 Canary Framework 核心导出和可用接口的快速参考。

## 1. 核心导出

```python
from canary_framework import (
    # 元数据装饰器
    service, 
    module, 
    config,

    # 容器引擎
    Canary,
)
```

## 2. 核心 Web 扩展导出

所有 HTTP 和 OpenAPI 相关的能力均位于 `web` 包内：

```python
from canary_framework.core.web.router import Router
```

## 3. 装饰器 API

### `@service()`
不需要任何参数，直接作用于类。将该类提升为受容器接管的服务组件。

### `@module(services=..., config_cls=...)`
- `services`: `list[type]`，包含需要在这个模块下启动的子模块或子服务。
- `config_cls`: `type[CanaryConfig]`，仅能在根模块使用，用于全局配置挂载。

## 4. 容器引擎

### `Canary(root_module)`
- 接受一个被 `@module()` 或 `@service()` 标记的类实例。
- 自动进行拓扑排序并建立 DI 依赖网。
- 本身符合 ASGI 3.0 规范，可以直接喂给 `uvicorn` 执行。

## 5. Web 路由 (Router)

### `Router(prefix="", tags=None)`
- 用于服务内的属性声明：`router = Router(prefix="/api")`。
- 提供 HTTP 方法修饰器：
  - `@router.get(path, request_model=...)`
  - `@router.post(path, request_model=...)`
  - `@router.put(...)`
  - `@router.delete(...)`
  - `@router.patch(...)`
