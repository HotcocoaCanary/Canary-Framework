# Quickstart

Let's build a purely native, minimalistic blog backend using Canary Framework in 5 minutes.

## 1. Writing Infrastructure Services

First, define a pure dependency service that doesn't need routing (like a database):

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

## 2. Writing Web Services

Now, create a service that has routes and depends on the `Database`. Notice how we utilize the type annotation `db: Database` for dependency injection:

```python
# api.py
from canary_framework import service
from canary_framework.core.web.router import Router
from .database import Database

@service()
class BlogApi:
    router = Router(prefix="/api/posts")
    db: Database  # Just annotate the type, and the framework injects the Database during startup!

    @router.get("/")
    async def get_posts(self):
        # You can use self.db directly; it is guaranteed to be ready
        data = await self.db.query()
        return {"posts": data}
```

## 3. Writing Root Module & Container Bootstrapping

Finally, package them together using `@module()`, then pass them to the `Canary` container:

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

# The Canary container takes over everything
app = Canary(AppModule())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## 4. Run
```bash
python main.py
```
- You will see clear topological sorting boot logs in the console, along with the execution of the `Database connecting...` lifecycle hook.
- Visit `http://127.0.0.1:8000/api/posts/` to see your blog data.
- Visit `http://127.0.0.1:8000/docs` to see the generated OpenAPI documentation!
