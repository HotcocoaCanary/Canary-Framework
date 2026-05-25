# 依赖注入

## 最小写法：声明依赖

```python
@service(name="B", deps=[A])
class B:
    def work(self):
        self.a.do()            # A 自动注入为 self.a
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
实例化 → 依赖注入 → 配置加载 → on_init(ctx)
```

在 `on_init` 中已可访问所有注入的依赖。

## 启动顺序

Kahn 拓扑排序：被依赖的服务先启动，无依赖的服务最先启动。检测到循环依赖时抛出 `RuntimeError`。
