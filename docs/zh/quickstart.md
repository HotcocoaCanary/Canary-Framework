# 快速入门

本指南将带您构建一个完整的 Canary Framework 应用程序。

## 1. 环境准备

首先，确保您安装了 Python 3.12+ 和 pip：

```bash
python --version  # 应显示 Python 3.12+
pip --version     # 应显示 pip 已安装
```

安装 Canary Framework：

```bash
pip install canary-framework
```

## 2. 项目结构

让我们创建一个简单的博客应用：

```
my_blog/
├── main.py
└── services/
    ├── __init__.py
    ├── database.py
    ├── auth.py
    └── posts.py
```

## 3. 数据库服务

首先，创建一个数据库服务：

```python
# services/database.py
from canary_framework import service, after_config, before_shutdown
from canary_framework.core.service import ServiceBase

@service()
class Database(ServiceBase):
    def __init__(self):
        self.connection = None

    @after_config
    async def connect(self):
        self.connection = "connected"
        print("Database connected")

    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")

    async def query(self, sql):
        return f"Executed: {sql}"
```

- `@service()` 自动将服务命名为 `DatabaseService`
- 生命周期钩子 `@after_config` 和 `@before_shutdown` 管理连接的建立和拆除

## 4. 认证服务

创建一个依赖数据库的认证服务：

```python
# services/auth.py
from canary_framework import service, after_init
from canary_framework.core.service import ServiceBase
from .database import Database

@service()
class Auth(ServiceBase):
    db: Database  # 通过注解声明依赖

    def __init__(self):
        self.users = {}

    @after_init
    async def init_default_users(self):
        self.users = {
            "admin": {"name": "Admin", "role": "admin"},
            "user": {"name": "User", "role": "user"}
        }

    async def verify_user(self, username):
        return username in self.users

    async def get_user(self, username):
        return self.users.get(username)
```

- `db: Database` 声明对 `Database` 的依赖 — 框架自动解析并注入
- 注入的依赖通过 `self.db` 访问（使用注解键名）

## 5. 文章路由

构建博客文章的 Web 路由：

```python
# services/posts.py
from canary_framework import router, get, post, put, delete
from canary_framework.core.router import RouterBase
from pydantic import BaseModel, Field
from .auth import Auth
from .database import Database

class PostCreate(BaseModel):
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

class PostResponse(BaseModel):
    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

@router(prefix="/api/posts", tags=["Posts"])
class Posts(RouterBase):
    db: Database  # 自动注入
    auth: Auth    # 自动注入

    def __init__(self):
        self.posts = [
            {"id": 1, "title": "First Post", "content": "Hello World!", "author": "admin"}
        ]

    @get("/", summary="List posts", description="Get all blog posts")
    async def list_posts(self):
        return {"posts": self.posts}

    @get("/{post_id}",
         summary="Get post",
         description="Get post details by ID",
         response_model=PostResponse)
    async def get_post(self, post_id: int):
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            return post
        return {"error": "Post not found"}, 404

    @post("/",
          summary="Create post",
          description="Create a new blog post",
          request_model=PostCreate,
          response_model=PostResponse)
    async def create_post(self, body: PostCreate):
        new_post = {
            "id": len(self.posts) + 1,
            "title": body.title,
            "content": body.content,
            "author": body.author
        }
        self.posts.append(new_post)
        return new_post, 201

    @put("/{post_id}",
         summary="Update post",
         description="Update post content",
         request_model=PostCreate,
         response_model=PostResponse)
    async def update_post(self, post_id: int, body: PostCreate):
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            post.update({
                "title": body.title,
                "content": body.content,
                "author": body.author
            })
            return post
        return {"error": "Post not found"}, 404

    @delete("/{post_id}", summary="Delete post", description="Delete a post")
    async def delete_post(self, post_id: int):
        self.posts = [p for p in self.posts if p["id"] != post_id]
        return {"message": "Post deleted"}
```

与旧版 API 的关键区别：

- 路径参数如 `{post_id}` 自动绑定 — 作为函数参数声明（`post_id: int`）
- `request_model` 使请求体自动解析并作为 `body` 参数传入
- 不再需要 `self, request` — 参数自动注入
- 不再需要 `deps` 参数 — 依赖通过注解声明（`db: Database`, `auth: Auth`）

## 6. 主应用模块

将所有内容组合到主模块中：

```python
# main.py
from canary_framework import module
from canary_framework.core.module import ModuleBase
from services.database import Database
from services.auth import Auth
from services.posts import Posts

@module(services=[Database, Auth, Posts])
class BlogApp(ModuleBase):
    pass

async def setup():
    app = BlogApp()
    await app.configure()
    await app.init()
    return app

if __name__ == "__main__":
    import asyncio
    import uvicorn

    app = asyncio.run(setup())
    uvicorn.run(app, lifespan="on")
```

- `@module(services=[...])` — 无需 `name=` 参数；自动命名为 `BlogAppModule`
- 子模块通过类属性名访问：`app.Database`, `app.Auth`, `app.Posts`

## 7. 运行应用

```bash
python main.py
```

测试您的 API：

```bash
# 列出所有文章
curl http://localhost:8000/api/posts/

# 获取单篇文章
curl http://localhost:8000/api/posts/1

# 创建新文章
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post", "content": "Another post!", "author": "user"}'

# 更新文章
curl -X PUT http://localhost:8000/api/posts/2 \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post (Updated)", "content": "Updated content", "author": "user"}'

# 删除文章
curl -X DELETE http://localhost:8000/api/posts/2
```

## 8. 访问 OpenAPI 文档

启动应用后，可以访问以下端点：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`
- **OpenAPI JSON**：`http://localhost:8000/openapi.json`

## 您学到了什么

- 使用 `@service()` 定义服务 — 无需手动指定名称
- 使用 `@router(prefix=...)` 和 HTTP 方法装饰器创建路由
- 通过 Python 类型注解声明依赖（`db: Database`）
- 路由参数从路径、查询和请求体自动绑定
- 使用 `@module(services=[...])` 组合所有内容
- 使用生命周期钩子进行初始化和清理
- 使用 Pydantic 模型进行请求验证
- **框架日志自动配置** — 无需 `logging.basicConfig()`。
  在配置对象上设置 `log_level` 来控制详细程度（默认：`"INFO"`）
- **配置** — 使用 `@config` 和 `CanaryConfig` 自定义主机、端口、日志级别、OpenAPI 设置等：
  ```python
  from canary_framework import config
  from canary_framework.common.config import CanaryConfig

  @config
  class AppConfig(CanaryConfig):
      host: str = "0.0.0.0"
      port: int = 8080
      openapi_title: str = "My Blog API"
      log_level: str = "DEBUG"

  async def setup():
      cfg = AppConfig()
      app = BlogApp()
      await app.configure(cfg)
      await app.init()
      return app, cfg
  ```

## 下一步

探索详细文档：
- [服务](./services.md)
- [模块](./modules.md)
- [Web 路由](./web.md)
- [依赖注入](./dependency-injection.md)
- [生命周期](./lifecycle.md)
- [核心概念](./core.md)
- [API 参考](./api-reference.md)
