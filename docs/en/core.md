# Architecture

## Declaration layer

`@service`, `@router`, and `@module` validate explicit base-class inheritance and attach immutable metadata. Top-level HTTP decorators attach immutable route specifications without wrapping handlers.

## Runtime layer

`ServiceBase` owns the async lifecycle state machine and domain/DI behavior. `RouterBase` adds route collection and can become a runtime root. `ModuleBase` owns child composition and recursive route collection.

Only initialized runtime-root Router/Module instances serve HTTP through ASGI.

## Dependency engine

Each root/scope has a registry. Dependency annotations form a validated directed graph. Topological ordering drives initialization/startup and reverse shutdown. Parent lookup, sibling isolation, and promotion are explicit.

## Route pipeline

1. Decorators create `RouteSpec` values.
2. Router/Module traversal creates `ResolvedRoute` values with bound handlers and composed context.
3. Parameter analysis and validation produce validated routes.
4. OpenAPI and ASGI compilers consume the same validated route sequence.
5. The immutable Assembly is memoized on the initialized runtime root.

This single pipeline prevents request binding and OpenAPI from interpreting routes differently.
