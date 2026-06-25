# Lifecycle Management

Canary Framework provides a minimalistic yet powerful lifecycle system. You simply declare specific methods by name in your class, and the engine will automatically trigger them at the appropriate stage of the topological sort. No need for cumbersome `@before_startup` hook decorators.

## Lifecycle Hooks

Your service (or module) can optionally implement the following three methods:

### 1. `def init(self) / async def init(self)`
- **Triggered**: Immediately after all dependencies have been injected via `setattr`.
- **Purpose**: Used for the service's own initialization logic. When execution reaches here, you are guaranteed that all external dependencies are ready.

### 2. `async def startup(self)`
- **Triggered**: When the ASGI Lifespan receives a `startup` event, or during the system main boot phase. Executed in **forward topological order** (i.e., base services start first, dependent services start later).
- **Purpose**: Establishing long-lived database connections, starting background tasks, initializing external network resources, etc.

### 3. `async def shutdown(self)`
- **Triggered**: When the ASGI Lifespan receives a `shutdown` event, or during system teardown. Executed in **reverse topological order** (i.e., dependent services tear down first, base services tear down last).
- **Purpose**: Graceful shutdown, disconnecting from databases, releasing ports, stopping background tasks, etc.

## Example

```python
from canary_framework import service
import asyncio

@service()
class Database:
    async def init(self):
        self.connection_string = "postgres://..."

    async def startup(self):
        print(f"Connecting to {self.connection_string}")
        await asyncio.sleep(1) # Simulate connection

    async def shutdown(self):
        print("Disconnecting from database...")
```
