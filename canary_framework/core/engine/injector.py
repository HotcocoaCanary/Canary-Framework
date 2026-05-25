"""依赖注入引擎 —— 将声明的依赖服务实例注入到目标服务实例的属性上。

依赖类名（PascalCase）通过 to_snake() 转换为属性名:
    DBService     → db_service
    UserService   → user_service
    HTTPSConn     → https_conn
"""

from __future__ import annotations

import logging

from canary_framework.core.registry.registry import Registry, ServiceEntry
from canary_framework.core.utils.naming import to_snake

_log = logging.getLogger("cf.di")


def inject_deps(
    instance: object,
    entry: ServiceEntry,
    registry: Registry,
) -> None:
    """将 deps 中声明的依赖服务实例，按类名 snake_case 注入到 instance 的属性上。

    遍历 entry.deps 中的每个依赖类:
        1. 从 Registry 按类对象查找依赖的 ServiceEntry
        2. to_snake(dep_cls.__name__) 生成属性名
        3. setattr(instance, attr_name, dep_instance)

    注入发生在 on_init 之前，因此 on_init 中已可访问注入的属性。
    """
    for dep_cls in entry.deps:
        dep_entry = registry.get_by_class(dep_cls)
        attr_name = to_snake(dep_cls.__name__)
        setattr(instance, attr_name, dep_entry.instance)
        _log.debug("  %s  →  self.%s", dep_cls.__name__, attr_name)
