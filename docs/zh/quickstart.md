# 快速入门

本指南将带您构建一个完整的 Canary 框架应用程序。

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

首先，让我们创建一个数据库服务：

```python
# services/database.py
from canary_framework import service, after_config, before_shutdown

@service(name="database")
class DatabaseService:
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

## 4. 认证服务

现在，让我们创建一个依赖于数据库的认证服务：

```python
# services/auth.py
from canary_framework import service, after_init
from .database import DatabaseService

@service(name="auth", deps=[DatabaseService])
class AuthService:
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

## 5. 文章路由

让我们为博客文章构建一个 Web 路由：

```python
# services/posts.py
from canary_framework import router, get, post, put, delete
from pydantic import BaseModel, Field
from .auth import AuthService
from .database import DatabaseService

class PostCreate(BaseModel):
    title: str = Field(description="文章标题")
    content: str = Field(description="文章内容")
    author: str = Field(description="作者")

class PostResponse(BaseModel):
    id: int = Field(description="文章ID")
    title: str = Field(description="文章标题")
    content: str = Field(description="文章内容")
    author: str = Field(description="作者")

@router(name="posts", prefix="/api/posts", deps=[AuthService, DatabaseService], tags=["Posts"])
class PostsRouter:
    def __init__(self):
        self.posts = [
            {"id": 1, "title": "第一篇文章", "content": "Hello World!", "author": "admin"}
        ]
    
    @get("/", summary="获取文章列表", description="获取所有博客文章")
    async def list_posts(self, request):
        return {"posts": self.posts}
    
    @get("/{post_id}", 
         summary="获取单篇文章", 
         description="根据ID获取文章详情",
         response_model=PostResponse)
    async def get_post(self, request):
        post_id = int(request.path_params["post_id"])
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            return post
        return {"error": "文章未找到"}, 404
    
    @post("/", 
          summary="创建文章", 
          description="创建新博客文章",
          request_model=PostCreate,
          response_model=PostResponse)
    async def create_post(self, request, post_data: PostCreate):
        new_post = {
            "id": len(self.posts) + 1,
            "title": post_data.title,
            "content": post_data.content,
            "author": post_data.author
        }
        self.posts.append(new_post)
        return new_post, 201
    
    @put("/{post_id}",
         summary="更新文章",
         description="更新文章内容",
         request_model=PostCreate,
         response_model=PostResponse)
    async def update_post(self, request, post_data: PostCreate):
        post_id = int(request.path_params["post_id"])
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            post.update({
                "title": post_data.title,
                "content": post_data.content,
                "author": post_data.author
            })
            return post
        return {"error": "文章未找到"}, 404
    
    @delete("/{post_id}", summary="删除文章", description="删除指定文章")
    async def delete_post(self, request):
        post_id = int(request.path_params["post_id"])
        self.posts = [p for p in self.posts if p["id"] != post_id]
        return {"message": "文章已删除"}
```

## 6. 主应用模块

现在，让我们把所有内容组合到我们的主模块中：

```python
# main.py
from canary_framework import module
from services.database import DatabaseService
from services.auth import AuthService
from services.posts import PostsRouter

@module(name="blog_app", services=[DatabaseService, AuthService, PostsRouter])
class BlogApp:
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:BlogApp", host="0.0.0.0", port=8000, reload=True)
```

## 7. 运行应用

```bash
python main.py
```

现在您可以测试您的 API：

```bash
# 列出所有文章
curl http://localhost:8000/api/posts/

# 获取单篇文章
curl http://localhost:8000/api/posts/1

# 创建新文章
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "第二篇文章", "content": "另一篇文章！", "author": "user"}'

# 更新文章
curl -X PUT http://localhost:8000/api/posts/2 \
  -H "Content-Type: application/json" \
  -d '{"title": "第二篇文章（更新）", "content": "更新后的内容", "author": "user"}'

# 删除文章
curl -X DELETE http://localhost:8000/api/posts/2
```

## 8. 访问 OpenAPI 文档

启动应用后，可以访问自动生成的 API 文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## 您学到了什么

- 如何使用 `@service` 定义服务
- 如何使用 `@router` 和 HTTP 方法装饰器创建路由
- 如何声明服务之间的依赖
- 如何使用 `@module` 将所有内容组合成一个模块
- 如何使用生命周期钩子进行初始化和清理
- 如何使用 Pydantic 模型进行请求验证
- 如何自动生成 OpenAPI 文档
- **框架日志自动配置** — 无需手动调用 `logging.basicConfig()`。
  在配置对象上设置 `cf_log_level` 来控制详细程度（默认：`"INFO"`）

## 下一步

探索详细文档：
- [服务](./services.md)
- [模块](./modules.md)
- [Web 路由](./web.md)
- [依赖注入](./dependency-injection.md)
- [生命周期](./lifecycle.md)
- [核心概念](./core.md)
- [API 参考](./api-reference.md)