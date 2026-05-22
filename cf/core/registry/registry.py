"""
注册中心 —— 服务的注册与查找。

包含两个核心类：
1. ServiceEntry：单个服务/模块的注册项，记录其元数据和运行时状态
2. Registry：注册表，管理所有 ServiceEntry，按名称和类型双向索引
"""
from __future__ import annotations

from typing import Any


class ServiceEntry:
    """
    服务注册项 —— 保存一个服务或模块的完整元数据和运行时信息。

    该对象在 _collect 阶段创建，在 _init 阶段填充运行时数据。

    字段说明：
        cls:             被 @service 或 @module 装饰的原始类
        instance:        类的实例对象（在 Registry.register 时通过 cls() 创建）
        name:            服务/模块的名称（@service 或 @module 声明的 name）
        deps:            依赖的服务类列表（@service(deps=[...]) 声明的原始类）
        config_cls:      由 @config 装饰的配置类（BaseSettings 子类）
                         None 时若存在父模块，则继承父模块的 config_cls
        is_module:       是否为模块
        sub_services:    如果是模块，记录其包含的子服务和子模块的类列表
        dep_names:       依赖的名称列表（由 deps 中的类名转换而来），用于拓扑排序
        config_instance: 配置类的实例（在 _init 阶段创建），None 表示无配置或尚未初始化
    """

    def __init__(
        self,
        cls: type,
        instance: object,
        name: str,
        deps: list[type],
        config_cls: type | None,
        is_module: bool = False,
        sub_services: list[type] | None = None,
    ) -> None:
        self.cls = cls
        self.instance = instance
        self.name = name
        self.deps = deps
        self.config_cls = config_cls
        self.is_module = is_module
        self.sub_services = sub_services or []
        self.dep_names: list[str] = []
        self.config_instance: object | None = None


class Registry:
    """
    注册中心 —— 管理所有服务的注册、查找和查询。

    内部使用两个字典实现双向索引：
    1. _by_name:  按服务名称索引（name → ServiceEntry），名称必须唯一
    2. _by_class: 按类对象索引（cls → ServiceEntry），类对象必须唯一
    """

    def __init__(self) -> None:
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    def register(
        self,
        cls: type,
        *,
        is_module: bool = False,
        sub_services: list[type] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        注册一个服务或模块到注册中心。

        参数：
            cls:          被 @service 或 @module 装饰的类
            is_module:    是否为模块
            sub_services: 子服务列表（仅模块使用）
            meta:         元数据字典，包含 name, deps, config_cls
        """
        if cls in self._by_class:
            return

        if meta is None:
            from cf.core.decorators.service import get_service_meta
            from cf.core.decorators.module import get_module_meta

            if is_module:
                meta = get_module_meta(cls)
            else:
                meta = get_service_meta(cls)

        name = meta["name"]
        if name in self._by_name:
            raise ValueError(f"Service/Module '{name}' is already registered")

        instance = cls()
        entry = ServiceEntry(
            cls=cls,
            instance=instance,
            name=name,
            deps=meta.get("deps", []),
            config_cls=meta.get("config_cls"),
            is_module=is_module,
            sub_services=meta.get("services", []) if is_module else None,
        )
        entry.dep_names = [
            d if isinstance(d, str) else d.__cf_name__ for d in entry.deps
        ]

        self._by_name[name] = entry
        self._by_class[cls] = entry

    def get_by_name(self, name: str) -> ServiceEntry:
        return self._by_name[name]

    def get_by_class(self, cls: type) -> ServiceEntry:
        return self._by_class[cls]

    def get_instance(self, cls: type) -> object:
        return self._by_class[cls].instance

    def has(self, cls: type) -> bool:
        return cls in self._by_class

    def all_entries(self) -> list[ServiceEntry]:
        return list(self._by_name.values())

    def names(self) -> list[str]:
        return list(self._by_name.keys())
