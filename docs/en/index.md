# Canary Framework

Canary Framework is a lightweight, aspect-oriented, pure decorator-driven Python asynchronous infrastructure framework.
Unlike traditional web frameworks, the core soul of Canary is a **pure Dependency Injection (DI) and lifecycle container**, designed to build complex, highly scalable, and modular applications (such as Agentic systems or complex web backends).

## Core Features

- **Pure Decorator Architecture**: No base classes required. Simply use `@service()` or `@module()` to place any plain class under the framework's management.
- **Ultimate Dependency Injection (DI)**: Fully automated DI mechanism based on Python Type Hints. Zero intrusion, zero explicit calls.
- **Kahn's Topological Sort**: The engine computes a bulletproof service startup order using graph algorithms, completely avoiding cyclic dependency deadlocks.
- **Micro-kernel & Pluggability**: The core strictly handles dependencies and lifecycles (`init`, `startup`, `shutdown`). Capabilities like HTTP Routing (Router) and OpenAPI are isolated into the `core/web/` plugin package.
- **Flat Routing System**: Although primarily a DI container, it includes a native, minimalistic Starlette HTTP router with blazing-fast performance and automatic OpenAPI 3.0.3 documentation generation.
