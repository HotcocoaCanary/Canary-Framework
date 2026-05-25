from canary_framework.core.decorators.service import service
from canary_framework.core.engine.injector import inject_deps
from canary_framework.core.registry.registry import Registry


def test_inject():
    @service("db")
    class DB:
        connected = True

    @service("user", deps=[DB])
    class User:
        pass

    reg = Registry()
    reg.register(DB)
    reg.register(User)
    inject_deps(reg.get_by_name("user").instance, reg.get_by_name("user"), reg)
    assert reg.get_by_name("user").instance.db.connected is True
