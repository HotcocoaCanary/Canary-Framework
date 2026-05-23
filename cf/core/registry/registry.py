# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cf.core.engine.context import Context


class ServiceEntry:
    # 服务/模块的单条注册记录，保存装饰器元数据和运行时填充的实时信息

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
        self.parent_entry: ServiceEntry | None = None
        self.context: Context | None = None
        # 缓存 find_hooks 的结果，每个 entry 只查一次 dir(instance)
        self._hooks: dict | None = None


class Registry:
    # 注册中心：管理所有服务的注册、查找和遍历

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
        if cls in self._by_class:
            return

        if meta is None:
            from cf.core.decorators.service import get_service_meta
            from cf.core.decorators.module import get_module_meta
            meta = get_module_meta(cls) if is_module else get_service_meta(cls)

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
            d if isinstance(d, str) else getattr(d, '__cf_name__', d.__name__)
            for d in entry.deps
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
