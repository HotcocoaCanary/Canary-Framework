# 依赖注入

## 最小写法：声明依赖

```python
@service(name="B", deps=[A])
class B:
    def work(self) -> str:
        return self.a.do()            # A 自动注入为 self.a
```

## 注入规则

类名 → snake_case → 属性名：

| 依赖类 | 注入为 |
|--------|--------|
| `DBService` | `self.db_service` |
| `UserService` | `self.user_service` |
| `DataSetAdminService` | `self.data_set_admin_service` |

## 注入时机

```
app.config()→ wiring + on_config() → app.init()→ 依赖注入 → on_init()
```

在 `on_config` 中可访问 config 属性，在 `on_init` 中可访问所有注入的依赖。

## Config 属性访问

通过 `self.config` 访问传入 `app.config(config=...)` 的配置实例，树中所有服务和模块均可用：

```python
from canary_framework import config

@config
class AppConfig:
    url: str = "localhost"
    pool_size: int = 10

@service(name="db")
class DBService:
    @on_config
    def setup(self) -> None:
        self.pool = connect(self.config.url)
```

## 启动顺序

Kahn 拓扑排序：被依赖的服务先启动，无依赖的服务最先启动。检测到循环依赖时抛出 `CircularDependencyError`：

```python
from canary_framework import CircularDependencyError

try:
    await app.init()
except CircularDependencyError as e:
    print(f"检测到循环依赖: {e}")
```

如果依赖的服务未找到，抛出 `ServiceNotFoundError`。

## 跨模块依赖

依赖解析在模块树中进行，服务可以依赖同一模块或其他模块中的服务：

```python
@module(name="ModuleA", services=[SvcA])
class ModuleA:
    pass

@module(name="ModuleB", services=[SvcB])
class ModuleB:
    pass

@service(name="SvcB", deps=[SvcA])  # 跨模块依赖，只要 SvcA 在全局已注册即可
class SvcB:
    svc_a: SvcA

@module(name="Root", services=[ModuleA, ModuleB])
class Root:
    pass
```
