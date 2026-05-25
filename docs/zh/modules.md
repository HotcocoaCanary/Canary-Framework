# 模块

## 最小写法

```python
from canary_framework import module

@module(name="App", services=[SvcA, SvcB])
class App:
    pass
```

## 完整写法

```python
from canary_framework import module, on_init, Context

@module(
    name="AppModule",
    config=AppConfig,           # 可选：子服务未声明 config 时自动继承
    services=[DBService, UserService],
)
class AppModule:
    @on_init
    def init(self, ctx: Context) -> None:
        pass                    # 模块也可以有生命周期钩子

    @on_start
    def start(self) -> None:
        pass
```

## config 继承规则

```python
@module(name="DBModule", config=DBConfig, services=[DBService])
class DBModule:
    pass

@service(name="DBService")              # 未声明 config → 继承父模块的 DBConfig
class DBService:
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
