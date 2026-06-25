# Architecture Philosophy & Core Engine

Canary Framework follows a highly decoupled **Micro-kernel & Pluggable** three-layer architecture:

```
 common/  ──►  decorators/  ──►      core/     ──► canary.py (Container Launcher)
(types,        (metadata)        (DI Registry)   
 errors)                               └──► web/ (Built-in HTTP Extension)
```

## Design Overview

1. **Core Engine**: Contains no business logic. It strictly handles lifecycle management, class metadata parsing, and seamless Dependency Injection via Kahn's algorithm.
2. **Pure Container**: The entire framework revolves around the `Canary` class. You simply provide an entry point root module marked with `@module()`, and the container takes over it and all child services.
3. **Plugin System (Web)**: HTTP routing and API documentation generation are no longer forcibly tied to the core engine. They are cohesively grouped under `core/web/` as a built-in extension. If you just want to build a CLI tool or headless Agent backend, you won't couple with Web logic at all.

## Container Bootstrapping

When you execute `Canary(AppModule())`, the engine performs the following actions:
1. **Dependency Collection**: Scans `AppModule` and all declared `services` top-down.
2. **Graph Construction**: Scans type hints on all classes to link references.
3. **Topological Sort**: Runs Kahn's algorithm to verify if circular dependencies exist and formulates a faultless instantiation order.
4. **Instantiation & Auto-Injection**: Instantiates `cls()` sequentially and uses `setattr` to inject required instances.
5. **Init Hook**: Triggers the `init()` method on each service (if present).
6. **Web Adapter (Optional)**: If the engine detects a `Router` instance on services, it compiles them into a native ASGI flat routing list.

## Why Pure Decorators?

Older versions (or many traditional frameworks) forced developers to inherit from base classes like `ServiceBase`. This heavily violates Inversion of Control (IoC), "kidnapping" user code.
Now, your code consists of pure native Python classes with zero framework inheritance baggage. The framework achieves true **zero intrusion**.
