# 模块

`@module` 内部调用 `@service` —— 模块也是服务。二者的元数据类型不同：`ModuleMeta` 扩展了 `ServiceMeta`，额外包含 `services` 列表。

## 最小写法

```python
from canary_framework import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

## 完整写法

```python
from canary_framework import module, on_init

@module(
    name="AppModule",
    services=[DBService, UserService],
)
class AppModule:
    @on_init
    def init(self) -> None:
        pass                    # 模块也可以有生命周期钩子

    @on_start
    def start(self) -> None:
        pass
```

## 模块嵌套

模块支持任意深度的嵌套：

```python
@module(name="Root", services=[
    SubModuleA,
    SubModuleB,
])
class Root:
    pass

@module(name="SubModuleA", services=[ServiceX, ServiceY])
class SubModuleA:
    pass
```

## 模块中包含路由

因为 `@router` 内部也调用 `@service`，路由类可以像普通服务一样放入模块的 `services` 列表：

```python
from canary_framework.web.fastapi import router

@router(prefix="/api")
class ApiRouter:
    @get("/ping")
    def ping(self) -> str:
        return "pong"

@module(name="App", services=[ApiRouter, DBService])
class AppModule:
    pass
```
