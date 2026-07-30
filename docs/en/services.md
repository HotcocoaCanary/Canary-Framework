# Services

A Service is a lifecycle-managed, dependency-injected domain object. It is not callable as ASGI and cannot be served.

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class Repository(ServiceBase):
    async def on_init(self) -> None:
        self.cache: dict[int, str] = {}

    def get(self, item_id: int) -> str | None:
        return self.cache.get(item_id)
```

Declare Service dependencies with class annotations. A Service may depend only on Services. A Router may depend on Services. Modules compose nodes rather than receiving injected Router/Module dependencies.

Services pass through `CREATED`, `INITIALIZED`, `STARTED`, and `STOPPED`; any failed transition sets `FAILED`. Public transitions reject illegal repeats. Initialization failure triggers best-effort reverse cleanup while preserving the original failure.

Keep tiny HTTP-specific logic in a Router. Extract logic into a Service when it needs reuse, independent tests, or its own resources.
