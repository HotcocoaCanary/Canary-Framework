# Web & HTTP Routing

Although Canary's core is a pure DI container, it includes a highly sophisticated built-in `web` plugin layer. This provides out-of-the-box, high-performance async HTTP routing based on Starlette, along with automated OpenAPI 3.0.3 specification generation.

## Declaring a Router

You simply instantiate a `Router` property inside your service class and use its method decorators to mount routes:

```python
from canary_framework import service
from canary_framework.core.web.router import Router
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    age: int

@service()
class UserService:
    # Declare the Router. All routes in this service will be prefixed with /users
    router = Router(prefix="/users", tags=["Users"])

    def __init__(self):
        self.db = {}

    @router.get("/{user_id}")
    async def get_user(self, user_id: int):
        # Path parameter user_id is automatically parsed
        return {"id": user_id, "data": self.db.get(user_id)}

    @router.post("/", request_model=UserCreate)
    async def create_user(self, body: UserCreate):
        # The request body is also automatically validated by Pydantic and injected
        self.db[1] = body
        return {"status": "created"}
```

## Flat Routing Architecture

Under the hood, the `Canary` container collects all service `Routers` during startup.
Unlike traditional nested Mount approaches, Canary uses **Flat Routing Compilation**: the engine flattens all child module and service paths into a one-dimensional native Starlette routing list.

**Advantages**:
1. **Extreme Performance**: Request matching depth becomes `O(1)`, without traversing multiple sub-route dispatchers.
2. **Collision Detection**: At the exact moment of startup, if any two services register the same HTTP method and path, the framework instantly raises a `ValueError: Route collision`.

## OpenAPI Document Generation

As long as your services contain routes, once you run the application, visiting `http://localhost:8000/docs` will directly present an automatically generated Swagger UI. This logic is encapsulated in the `core/web/openapi.py` extension package and is automatically hosted by the framework.
