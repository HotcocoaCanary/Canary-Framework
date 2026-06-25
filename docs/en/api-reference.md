# API Reference

This is a quick reference for the core exports and available interfaces in the Canary Framework.

## 1. Core Exports

```python
from canary_framework import (
    # Metadata Decorators
    service, 
    module, 
    config,

    # Container Engine
    Canary,
)
```

## 2. Core Web Extension Exports

All HTTP and OpenAPI-related capabilities reside within the `web` package:

```python
from canary_framework.core.web.router import Router
```

## 3. Decorator API

### `@service()`
Requires no arguments, directly applied to a class. Elevates the class to a service component managed by the container.

### `@module(services=..., config_cls=...)`
- `services`: `list[type]`, child modules or child services that need to be booted under this module.
- `config_cls`: `type[CanaryConfig]`, only used on the root module for mounting global configurations.

## 4. Container Engine

### `Canary(root_module)`
- Accepts a class instance marked with `@module()` or `@service()`.
- Automatically performs topological sorting and builds the DI dependency net.
- Fully compliant with the ASGI 3.0 specification, can be fed directly to `uvicorn` for execution.

## 5. Web Routing (Router)

### `Router(prefix="", tags=None)`
- Used for property declaration within services: `router = Router(prefix="/api")`.
- Provides HTTP method decorators:
  - `@router.get(path, request_model=...)`
  - `@router.post(path, request_model=...)`
  - `@router.put(...)`
  - `@router.delete(...)`
  - `@router.patch(...)`
