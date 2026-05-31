# 快速入门

本指南将带您构建一个完整的 Canary 框架应用程序。

## 1. 项目结构

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

## 2. 数据库服务

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
        # 模拟数据库连接
        self.connection = "connected"
        print("Database connected")
    
    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")
    
    async def query(self, sql):
        # 模拟查询执行
        return f"Executed: {sql}"
```

## 3. 认证服务

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
        # 初始化一些默认用户
        self.users = {
            "admin": {"name": "Admin", "role": "admin"},
            "user": {"name": "User", "role": "user"}
        }
    
    async def verify_user(self, username):
        return username in self.users
```

## 4. 文章路由

让我们为博客文章构建一个 Web 路由：

```python
# services/posts.py
from canary_framework import router, get, post, put, delete
from .auth import AuthService
from .database import DatabaseService

@router(name="posts", prefix="/api/posts", deps=[AuthService, DatabaseService])
class PostsRouter:
    def __init__(self):
        self.posts = [
            {"id": 1, "title": "第一篇文章", "content": "Hello World!"}
        ]
    
    @get("/")
    async def list_posts(self, request):
        return {"posts": self.posts}
    
    @get("/{post_id}")
    async def get_post(self, request):
        post_id = int(request.path_params["post_id"])
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            return post
        return {"error": "文章未找到"}, 404
    
    @post("/")
    async def create_post(self, request):
        data = await request.json()
        new_post = {
            "id": len(self.posts) + 1,
            "title": data.get("title"),
            "content": data.get("content")
        }
        self.posts.append(new_post)
        return new_post, 201
```

## 5. 主应用模块

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

# 运行应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:BlogApp", host="0.0.0.0", port=8000, reload=True)
```

## 6. 运行应用

```bash
python main.py
```

现在您可以测试您的 API：

```bash
# 列出所有文章
curl http://localhost:8000/posts/

# 获取单篇文章
curl http://localhost:8000/posts/1

# 创建新文章
curl -X POST http://localhost:8000/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "第二篇文章", "content": "另一篇文章！"}'
```

## 您学到了什么

- 如何使用 `@service` 定义服务
- 如何使用 `@router` 和 HTTP 方法装饰器创建路由
- 如何声明服务之间的依赖
- 如何使用 `@module` 将所有内容组合成一个模块
- 如何使用生命周期钩子进行初始化和清理

接下来，探索详细文档：
- [服务](./services.md)
- [模块](./modules.md)
- [Web 路由](./web.md)
- [依赖注入](./dependency-injection.md)
