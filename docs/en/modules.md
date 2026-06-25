# Modules

In the Canary Framework, Modules are responsible for the logical organization and aggregation of services. They themselves can also act as consumers of services.

## Defining a Module

Use the `@module()` decorator and pass the services belonging to this module to the `services` argument:

```python
from canary_framework import module
from .database import Database
from .users import UserRepository

@module(services=[Database, UserRepository])
class UserModule:
    # Modules can also have dependencies and lifecycles just like normal services
    repo: UserRepository

    async def init(self):
        print("User Module initialized.")
```

## Nesting and Architecture

In large applications, you can mount multiple sub-modules to a root module:

```python
from canary_framework import module
from .auth_module import AuthModule
from .user_module import UserModule

@module(services=[AuthModule, UserModule])
class AppModule:
    pass
```

Then, at startup, you just feed the `AppModule` to the `Canary` container:

```python
from canary_framework.canary import Canary
from myapp.app_module import AppModule

app = Canary(AppModule())
```
The container will automatically and recursively scan all services, performing a unified topological sort and dependency injection.
