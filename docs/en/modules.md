# Modules

A Module explicitly composes children, defines a dependency scope, and recursively aggregates Router routes. Modules cannot declare business endpoints.

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(children=(UsersRouter, AdminModule), prefix="/api", tags=("API",))
class App(ModuleBase):
    pass
```

`children` contains decorated Service, Router, or Module classes. List explicit composition nodes only; transitive Service dependencies are discovered from annotations.

Each nested Module gets a local registry. It reuses available parent Services, creates missing Services locally, and isolates sibling-local instances. To share one instance across siblings, list that Service at their common parent. Prefixes, tags, and security requirements compose outer-to-inner in declaration order.

A route-less Module is a valid composition node. If the runtime root has no Router descendants, it returns 404 and exposes no docs routes.
