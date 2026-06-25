# Services

A Service is the most fundamental building block in a Canary Framework application. Any regular Python class that contains business logic can be marked as a Service.

## Defining a Service

To define a service, simply apply the `@service()` decorator to a class:

```python
from canary_framework import service

@service()
class Database:
    async def query(self, sql: str):
        return {"status": "success", "sql": sql}
```

The framework will:
1. **Auto-register**: Register it as a resolvable target in the global DI container.
2. **Zero-intrusion**: You do not need to inherit from any base class. Your class remains a pure Python class.

## Declaring and Injecting Dependencies

The only thing you need to do is use Type Hints to tell the container what your service needs.

```python
from canary_framework import service

@service()
class UserRepository:
    db: Database  # The framework auto-injects the instantiated Database here

    async def get_user(self, user_id: int):
        return await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
```

## Lifecycle Hooks

Your service is free to define `init`, `startup`, and `shutdown` async hooks. See [Lifecycle Management](lifecycle.md).
