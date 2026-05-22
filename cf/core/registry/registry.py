from __future__ import annotations

from typing import Any


class ServiceEntry:
    def __init__(
        self,
        cls: type,
        instance: object,
        name: str,
        deps: list[type],
        config_cls: type | None,
        config_file_path: str | None,
        is_module: bool = False,
        sub_services: list[type] | None = None,
    ) -> None:
        self.cls = cls
        self.instance = instance
        self.name = name
        self.deps = deps
        self.config_cls = config_cls
        self.config_file_path = config_file_path
        self.is_module = is_module
        self.sub_services = sub_services or []
        self.dep_names: list[str] = []


class Registry:
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
            config_file_path=meta.get("config_file_path"),
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
