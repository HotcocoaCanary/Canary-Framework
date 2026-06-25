# 快速入门 (Quickstart)

让我们在 5 分钟内使用 Canary Framework 构建一个纯原生的极简博客后台。

## 1. 编写基础设施服务

首先，定义一个不需要路由的纯依赖服务（比如数据库）：

```python
# database.py
import asyncio
from canary_framework import service

@service()
class Database:
    async def startup(self):
        print("Database connecting...")
        await asyncio.sleep(0.5)
        print("Database connected!")

    async def query(self):
        return [{"id": 1, "title": "Hello Canary"}]
```

## 2. 编写 Web 服务

现在，创建一个含有路由并且依赖 `Database` 的服务。注意我们如何利用类型注解 `db: Database` 进行依赖注入：

```python
# api.py
from canary_framework import service
from canary_framework.core.web.router import Router
from .database import Database

@service()
class BlogApi:
    router = Router(prefix="/api/posts")
    db: Database  # 只要标注类型，框架就会在启动时把上面那个 Database 塞进来！

    @router.get("/")
    async def get_posts(self):
        # 这里可以直接使用 self.db，它绝对是就绪的
        data = await self.db.query()
        return {"posts": data}
```

## 3. 编写根模块与容器启动

最后，用 `@module()` 打包它们，然后传递给 `Canary` 容器：

```python
# main.py
import uvicorn
from canary_framework import module
from canary_framework.canary import Canary

from .database import Database
from .api import BlogApi

@module(services=[Database, BlogApi])
class AppModule:
    pass

# Canary 容器将接管这一切
app = Canary(AppModule())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## 4. 运行
```bash
python main.py
```
- 你将在控制台看到清晰的拓扑排序启动日志，以及 `Database connecting...` 的生命周期钩子执行。
- 访问 `http://127.0.0.1:8000/api/posts/` 即可看到你的博客数据。
- 访问 `http://127.0.0.1:8000/docs` 查看生成的 OpenAPI 文档！
