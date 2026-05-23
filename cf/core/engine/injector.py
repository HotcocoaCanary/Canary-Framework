# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

# to_snake：将 PascalCase 类名转换为 snake_case 属性名（如 DBService → db_service）
from cf.core.utils.naming import to_snake
# Registry：注册中心类型，用于从注册表中查找依赖的 ServiceEntry
from cf.core.registry.registry import Registry


def inject_deps(
    instance: object,   # 当前服务/模块的实例（需要被注入依赖的一方）
    entry,              # 当前服务/模块的 ServiceEntry（包含 deps: 依赖类列表）
    registry: Registry,  # 全局注册表（用于查找依赖服务的已注册实例）
) -> None:
    # 遍历当前服务声明的所有依赖类
    for dep_cls in entry.deps:
        # 从注册表中按类对象查找依赖服务的注册项
        # 此操作假定依赖服务已经完成注册（由拓扑排序保证顺序）
        dep_entry = registry.get_by_class(dep_cls)

        # 将依赖类的 PascalCase 类名转换为 snake_case 属性名
        # 例如：DBService → "db_service"，UserService → "user_service"
        # 该属性名即为注入后的访问名称
        attr_name = to_snake(dep_cls.__name__)

        # 使用 setattr 将依赖服务的实例注入到当前实例的属性上
        # 此后当前实例可通过 self.db_service、self.user_service 等直接访问依赖服务
        setattr(instance, attr_name, dep_entry.instance)
