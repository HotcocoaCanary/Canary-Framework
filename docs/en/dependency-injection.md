# Dependency Injection

Canary uses an extremely elegant **Type Hint-based, non-intrusive Dependency Injection system**.
You **do not** need to use complex dependency collectors or explicitly write `@depends` markers. The engine uses reflection on standard Python class attribute annotations to fully automate the heavy lifting.

## How to Declare Dependencies?

Simply annotate the class variables with the corresponding service types:

```python
from canary_framework import service

@service()
class Database:
    pass

@service()
class Cache:
    pass

@service()
class UserRepository:
    db: Database    # The framework will auto-inject the Database instance into self.db
    cache: Cache    # The framework will auto-inject the Cache instance into self.cache

    async def get_user(self, user_id):
        # You can safely use dependencies; they are guaranteed to be fully initialized!
        cached = await self.cache.get(f"user:{user_id}")
        ...
```

**Important Notes:**
- Injection happens during the class instantiation phase (after `__init__`, but before the `init` hook).
- The attribute name is entirely up to you (e.g., if you write `my_db: Database`, it will be injected as `self.my_db`).
- The injected type must also be a class decorated with `@service()` or `@module()`.

## Preventing Circular Dependencies

Canary has a strict built-in Directed Acyclic Graph (DAG) validation mechanism. If you write mutually dependent services:

```python
@service()
class A:
    b: 'B'

@service()
class B:
    a: 'A'
```

The engine will throw a `CircularDependencyError` instantly at container startup, rather than deadlocking during runtime.

## Initialization Safety Guarantee

Using topological sorting algorithms, Canary guarantees that a service's dependencies are **fully created and initialized before the service itself is created**. You will never encounter a scenario where a dependent component is a null pointer or uninitialized.
