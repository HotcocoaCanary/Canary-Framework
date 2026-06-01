# Quickstart

This guide will walk you through building a complete application with Canary Framework.

## 1. Prerequisites

First, ensure you have Python 3.12+ and pip installed:

```bash
python --version  # Should show Python 3.12+
pip --version     # Should show pip is installed
```

Install Canary Framework:

```bash
pip install canary-framework
```

## 2. Project Structure

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

## 3. Database Service

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
        self.connection = "connected"
        print("Database connected")
    
    @before_shutdown
    async def disconnect(self):
        self.connection = None
        print("Database disconnected")
    
    async def query(self, sql):
        return f"Executed: {sql}"
```

## 4. Auth Service

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
        self.users = {
            "admin": {"name": "Admin", "role": "admin"},
            "user": {"name": "User", "role": "user"}
        }
    
    async def verify_user(self, username):
        return username in self.users
    
    async def get_user(self, username):
        return self.users.get(username)
```

## 5. Posts Router

Let's build a web router for our blog posts:

```python
# services/posts.py
from canary_framework import router, get, post, put, delete
from pydantic import BaseModel, Field
from .auth import AuthService
from .database import DatabaseService

class PostCreate(BaseModel):
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

class PostResponse(BaseModel):
    id: int = Field(description="Post ID")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    author: str = Field(description="Author name")

@router(name="posts", prefix="/api/posts", deps=[AuthService, DatabaseService], tags=["Posts"])
class PostsRouter:
    def __init__(self):
        self.posts = [
            {"id": 1, "title": "First Post", "content": "Hello World!", "author": "admin"}
        ]
    
    @get("/", summary="List posts", description="Get all blog posts")
    async def list_posts(self, request):
        return {"posts": self.posts}
    
    @get("/{post_id}", 
         summary="Get post", 
         description="Get post details by ID",
         response_model=PostResponse)
    async def get_post(self, request):
        post_id = int(request.path_params["post_id"])
        post = next((p for p in self.posts if p["id"] == post_id), None)
        if post:
            return post
        return {"error": "Post not found"}, 404
    
    @post("/", 
          summary="Create post", 
          description="Create a new blog post",
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
         summary="Update post",
         description="Update post content",
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
        return {"error": "Post not found"}, 404
    
    @delete("/{post_id}", summary="Delete post", description="Delete a post")
    async def delete_post(self, request):
        post_id = int(request.path_params["post_id"])
        self.posts = [p for p in self.posts if p["id"] != post_id]
        return {"message": "Post deleted"}
```

## 6. Main Application Module

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:BlogApp", host="0.0.0.0", port=8000, reload=True)
```

## 7. Run the Application

```bash
python main.py
```

Now you can test your API:

```bash
# List all posts
curl http://localhost:8000/api/posts/

# Get a single post
curl http://localhost:8000/api/posts/1

# Create a new post
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post", "content": "Another post!", "author": "user"}'

# Update a post
curl -X PUT http://localhost:8000/api/posts/2 \
  -H "Content-Type: application/json" \
  -d '{"title": "Second Post (Updated)", "content": "Updated content", "author": "user"}'

# Delete a post
curl -X DELETE http://localhost:8000/api/posts/2
```

## 8. Access OpenAPI Documentation

After starting the application, you can access these endpoints:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## What You've Learned

- How to define services with `@service`
- How to create routers with `@router` and HTTP method decorators
- How to declare dependencies between services
- How to compose everything into a module with `@module`
- How to use lifecycle hooks for initialization and cleanup
- How to use Pydantic models for request validation
- How to automatically generate OpenAPI documentation

## Next Steps

Explore the detailed documentation:
- [Services](./services.md)
- [Modules](./modules.md)
- [Web Routing](./web.md)
- [Dependency Injection](./dependency-injection.md)
- [Lifecycle](./lifecycle.md)
- [Core Concepts](./core.md)
- [API Reference](./api-reference.md)