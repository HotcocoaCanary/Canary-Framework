# Quickstart

This guide will walk you through building a complete application with Canary Framework.

## 1. Project Structure

Let's create a simple blog application:

```
my_blog/
├── main.py
└── services/
    ├── __init__.py
    ├── database.py
    ├── auth.py
    └── posts.py
```

## 2. Database Service

First, let's create a database service:

```python
# services/database.py
from canary_framework import service, after_config, before_shutdown

@service(name="database")
class DatabaseService:
    def __init__(self):
        self.connection = None
    
    @after_config
    async def connect(self):
        # Simulate database connection
        self.connection = "connected"
        print("Database connected")
    
    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")
    
    async def query(self, sql):
        # Simulate query execution
        return f"Executed: {sql}"
```

## 3. Auth Service

Now, let's create an auth service that depends on the database:

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
        # Initialize some default users
        self.users = {
            "admin": {"name": "Admin", "role": "admin"},
            "user": {"name": "User", "role": "user"}
        }
    
    async def verify_user(self, username):
        return username in self.users
```

## 4. Posts Router

Let's build a web router for our blog posts:

```python
# services/posts.py
from canary_framework import router, get, post, put, delete
from .auth import AuthService
from .database import DatabaseService

@router(name="posts", prefix="/api/posts", deps=[AuthService, DatabaseService])
class PostsRouter:
    def __init__(self):
        self.posts = [
            {"id": 1, "title": "First Post", "content": "Hello World!"}
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
        return {"error": "Post not found"}, 404
    
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

## 5. Main Application Module

Now, let's compose everything into our main module:

```python
# main.py
from canary_framework import module
from services.database import DatabaseService
from services.auth import AuthService
from services.posts import PostsRouter

@module(name="blog_app", services=[DatabaseService, AuthService, PostsRouter])
class BlogApp:
    pass

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:BlogApp", host="0.0.0.0", port=8000, reload=True)
```

## 6. Run the Application

```bash
python main.py
```

Now you can test your API:

```bash
# List all posts
curl http://localhost:8000/posts/

# Get a single post
curl http://localhost:8000/posts/1

# Create a new post
curl -X POST http://localhost:8000/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post", "content": "Another post!"}'
```

## What You've Learned

- How to define services with `@service`
- How to create routers with `@router` and HTTP method decorators
- How to declare dependencies between services
- How to compose everything into a module with `@module`
- How to use lifecycle hooks for initialization and cleanup

Next, explore the detailed documentation:
- [Services](./services.md)
- [Modules](./modules.md)
- [Web Routing](./web.md)
- [Dependency Injection](./dependency-injection.md)
