# 快速开始

## 安装

```bash
pip install canary-framework          # 核心库
pip install canary-framework[web]     # 含 FastAPI 支持的完整安装
```

## 最小示例

```python
import asyncio
from canary_framework import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self) -> None:
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main() -> None:
    app = Canary(App)
    await app.init()
    await app.start()

asyncio.run(main())
```

不需要 `@config`、`@on_init`、`deps` —— 什么都没有也能跑。

## 完整示例

加上配置、依赖注入、Web 路由：

```python
import asyncio
from canary_framework import service, module, on_init, Context, config
from canary_framework.web.fastapi import get, router, WebCanary

# 配置
@config
class AppConfig:
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

# 路由
@router(prefix="/api", deps=[HelloService])
class APIRouter:
    hello_service: HelloService

    @get("/hello")
    async def hello(self) -> dict:
        return await self.hello_service.greet("world")

# 服务
@service(name="HelloService", config=AppConfig)
class HelloService:
    @on_init
    async def init(self, ctx: Context) -> None:
        pass

    @on_start
    def start(self) -> None:
        print("start")

    async def greet(self, name: str) -> str:
        return f"Hello, {name}!"

# 模块
@module(name="AppModule", config=AppConfig, services=[HelloService])
class AppModule:
    @get("/health")
    async def health(self) -> dict:
        return {"status": "ok"}


async def main() -> None:
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```
