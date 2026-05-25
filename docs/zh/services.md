# 服务

## 最小写法

```python
from canary_framework import service, on_start

@service(name="HelloService")
class HelloService:
    @on_start
    def start(self):
        print("started")
```

- `name`：全局唯一，必填
- 其他全可选

## 完整写法

```python
from canary_framework import service, on_init, Context

@service(
    name="UserService",         # 必填
    config=UserConfig,          # 可选：@config 装饰的配置类
    deps=[DBService],           # 可选：依赖列表，自动注入为 self.db_service
)
class UserService:
    @on_init
    def init(self, ctx: Context):
        ctx.config.db_url       # 访问配置
        self.db_service.query() # 使用已注入的依赖

    @on_start
    def start(self):
        pass

    @on_end
    def end(self):
        pass
```
