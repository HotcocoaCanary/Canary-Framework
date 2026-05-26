"""Dependency injection engine.

设计思路 (Design rationale):
    为什么注入发生在 ``on_init`` 之前？
    （Why inject before ``on_init``?）

    在 ``on_init`` 中，用户需要访问已注入的依赖来执行初始化逻辑。
    如果注入在 ``on_init`` 之后，用户必须在钩子中手动取 Registry 查找，
    这与框架"声明式依赖注入"的设计目标相悖。

    注入时机 (Injection timing):
        实例化 → 依赖注入 → 配置加载 → on_init(ctx)
                   ↑ 此时 self.db_service 已可用

    属性名生成 (Attribute name generation):
        ``DBService``     → ``self.db_service``
        ``UserService``   → ``self.user_service``
        ``HTTPSConn``     → ``self.https_conn``
        通过 ``to_snake()`` 将类名转为蛇形命名。
"""

from __future__ import annotations

from canary_framework.common._logging import get_logger
from canary_framework.common._types import ServiceEntry
from canary_framework.common.exceptions import DependencyInjectionError
from canary_framework.core.algorithms.naming import to_snake
from canary_framework.core.container.registry import Registry

_log = get_logger("di")


def inject_deps(
    instance: object,
    entry: ServiceEntry,
    registry: Registry,
) -> None:
    """Inject declared dependencies onto *instance*.

    将 entry.deps 中声明的依赖服务实例注入到目标实例的属性上。

    对每个依赖类：
        1. 通过 Registry 按类对象查找依赖的 ServiceEntry
        2. ``to_snake(cls.__name__)`` 生成属性名
        3. ``setattr(instance, attr_name, dep_instance)``

    Args:
        instance: 目标服务/模块实例。The target service/module instance.
        entry: 描述 *instance* 的 :class:`ServiceEntry`.
        registry: 全局 :class:`Registry`.

    Raises:
        DependencyInjectionError: 如果依赖的 ``instance`` 为 ``None``
            （依赖尚未初始化，通常说明启动顺序有误）。
    """
    for dep_cls in entry.deps:
        dep_entry = registry.get_by_class(dep_cls)
        # 防御性检查：依赖实例不应为 None
        if dep_entry.instance is None:
            raise DependencyInjectionError(
                f"Cannot inject '{dep_cls.__name__}' into '{entry.name}': "
                f"the dependency instance is None."
            )
        attr_name = to_snake(dep_cls.__name__)
        setattr(instance, attr_name, dep_entry.instance)
        _log.debug("  %s  →  self.%s", dep_cls.__name__, attr_name)
