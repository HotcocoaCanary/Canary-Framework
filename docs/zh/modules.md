# 模块

Module 显式组合子节点、定义依赖作用域，并递归聚合 Router 路由。Module 不允许声明业务端点。

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(children=(UsersRouter, AdminModule), prefix="/api", tags=("API",))
class App(ModuleBase):
    pass
```

`children` 可包含已装饰的 Service、Router、Module 类。只列显式组合节点；传递式 Service 依赖从注解发现。

每个嵌套 Module 有本地 registry：优先复用父 Service，缺失项在本地创建，兄弟本地实例互相隔离。需要跨兄弟共享时，将 Service 放到最近共同父 Module。prefix、tags、security 按由外到内、声明顺序组合。

无路由 Module 是合法组合节点。运行根没有任何 Router 后代时返回 404，且不暴露文档端点。
