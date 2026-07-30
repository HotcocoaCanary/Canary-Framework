# Dependency Injection

Declare dependencies with class annotations:

```python
@service()
class Repository(ServiceBase):
    pass

@router()
class Api(RouterBase):
    repository: Repository
```

The engine resolves transitive dependencies, validates direction, topologically orders nodes, instantiates each local class once, and assigns instances to annotated attributes.

## Direction rules

- Service → Service: allowed.
- Router → Service: allowed.
- Service → Router/Module: rejected.
- Router → Router/Module: rejected.
- Module: composes `children` and establishes scope; it is not an upward dependency target.

## Scopes

A child scope reuses matching parent Services. Missing Services are local to that scope; sibling scopes are isolated. Promote a Service by listing it at the nearest common parent when siblings must share one instance. Circular dependencies and unresolved forward references raise contextual framework errors during initialization.
