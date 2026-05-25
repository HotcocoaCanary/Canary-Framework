# 快速开始

## 安装

```bash
pip install git+https://github.com/HotcocoaCanary/Canary-Framework.git              # 核心库
pip install "git+https://github.com/HotcocoaCanary/Canary-Framework.git#egg=cf[web]" # 含 FastAPI
```

## 最小示例

```python
import asyncio
from cf import service, module, on_start, Canary

@service(name="hello")
class HelloService:
    @on_start
    def start(self):
        print("Hello from Canary!")

@module(name="App", services=[HelloService])
class App:
    pass

async def main():
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
from cf import service, module, on_init, on_start, Context, config
from cf.web.fastapi import web, get, router, WebCanary

# 配置
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    fastapi_title: str = "My API"

# 路由
@router(prefix="/api")
class APIRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service

    @get("/hello")
    async def hello(self):
        return await self.svc.greet("world")

# 服务
@web(routers=[APIRouter])
@service(name="HelloService", config=AppConfig)
class HelloService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        print("start")

    def greet(self, name: str):
        return f"Hello, {name}!"

# 模块
@web()
@module(name="AppModule", config=AppConfig, services=[HelloService])
class AppModule:
    pass

async def main():
    app = WebCanary(AppModule)
    await app.init()
    await app.start()

asyncio.run(main())
```
