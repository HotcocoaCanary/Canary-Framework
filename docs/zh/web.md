# Web 与 HTTP 路由 (Web & HTTP Routing)

虽然 Canary 的核心是一个纯粹的 DI 容器，但它内置了极高水准的 `web` 插件层，为你提供开箱即用的、基于 Starlette 的高性能异步 HTTP 路由，以及自动化的 OpenAPI 3.0.3 规范导出。

## 声明 Router

你只需要在服务类里实例化一个 `Router` 属性，并使用方法装饰器来挂载路由：

```python
from canary_framework import service
from canary_framework.core.web.router import Router
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    age: int

@service()
class UserService:
    # 声明 Router，所有该服务的路由都会加上 /users 前缀
    router = Router(prefix="/users", tags=["Users"])

    def __init__(self):
        self.db = {}

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        # 路径参数 user_id 会自动解析
        return {"id": user_id, "data": self.db.get(user_id)}

    @router.post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        # 请求体也会自动通过 Pydantic 校验并注入
        self.db[1] = body
        return {"status": "created"}
```

## 扁平化路由架构 (Flat Routing)

在引擎底层的实现中，`Canary` 容器会在启动时收集所有的服务 `Router`。
不同于传统的嵌套 Mount 方式，Canary 采用了 **扁平化路由编译 (Flat Routing)** 技术：引擎会将所有子模块和服务的路径打平，编译成一维的原生 Starlette 路由列表。

**优势**：
1. **极致性能**：请求匹配深度变成了 `O(1)`，无需跨越多层子路由分发。
2. **冲突检测**：在启动瞬间，如果有任何两个服务注册了相同的 HTTP 方法和路径，框架会立刻抛出 `ValueError: Route collision` 异常。

## OpenAPI 文档生成

只要你的服务包含路由，当你运行应用后，访问 `http://localhost:8000/docs` 就能直接查看到自动生成的 Swagger UI。这部分的逻辑封装在 `core/web/openapi.py` 扩展包内，由框架自动托管。
