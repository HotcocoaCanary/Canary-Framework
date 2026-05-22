"""
依赖注入引擎 —— 将依赖服务的实例注入到当前服务实例的属性上。

注入规则：
    依赖类名（PascalCase）→ 转换为 snake_case → 作为属性名设置到实例上

    例如：
        B.deps = [DBService]
        → B 实例上设置 self.db_service = DBService 的实例

这样服务就可以通过 self.<snake_case_dep> 直接访问依赖的服务，
无需手动构造函数。
"""
from __future__ import annotations

from cf.core.utils.naming import to_snake
from cf.core.registry.registry import Registry


def inject_deps(
    instance: object, entry, registry: Registry
) -> None:
    """
    将依赖的服务实例注入到当前实例。

    参数：
        instance:  当前服务/模块的实例对象（接收端）
        entry:     注册项（包含 deps 依赖类列表和 dep_names 依赖名称列表）
        registry:  全局注册表（用于查找依赖的已注册实例）

    注入过程：
        遍历 entry.deps（依赖的原始类列表）：
        1. 通过 registry.get_by_class(dep_cls) 找到依赖的注册项
        2. 通过 to_snake(dep_cls.__name__) 生成属性名
           （如 DBService → db_service, UserService → user_service）
        3. 使用 setattr 将依赖的实例注入到当前实例

    注意：
        注入发生在 _init 阶段，on_init 钩子调用之前，因此 on_init 内部已可用
        注入的属性
    """
    for dep_cls in entry.deps:
        # 从注册表中获取依赖的 ServiceEntry
        dep_entry = registry.get_by_class(dep_cls)
        # 将依赖类名转换为 snake_case 作为属性名
        attr_name = to_snake(dep_cls.__name__)
        # 将依赖的实例注入到当前实例
        setattr(instance, attr_name, dep_entry.instance)
