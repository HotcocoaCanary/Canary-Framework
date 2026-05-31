"""服务注册表实现。

提供服务注册、查找和迭代功能，支持父子注册表继承。

Registry writes happen only during ``configure`` (single-threaded),
after which it is read-only. No thread-safety needed for the
"write-once, read-many" pattern.

Service registry implementation.

Provides service registration, lookup, and iteration with parent-child inheritance.
"""

from __future__ import annotations

from collections.abc import Iterator

from canary_framework.common import (
    CF_NAME_ATTR,
    ServiceEntry,
    ServiceMeta,
    ServiceNotFoundError,
    get_module_meta,
    get_service_meta,
)


class Registry:
    """服务注册表，支持父子继承。

    注册表存储服务条目，支持通过名称或类查找。
    如果在当前注册表中找不到服务，会递归查找父注册表。

    Central registry — O(1) lookup by name or class, with parent chaining.
    """

    def __init__(self, parent: Registry | None = None) -> None:
        """初始化注册表。

        Args:
            parent: 父注册表，用于继承查找。

        Initialize the registry.

        Args:
            parent: Parent registry for inheritance lookups.
        """
        self.parent: Registry | None = parent
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    def register(self, cls: type, *, meta: ServiceMeta | None = None) -> None:
        """注册一个服务（幂等操作）。

        如果类已注册，则跳过。

        Args:
            cls: 服务类。
            meta: 服务元数据（可选）。

        Raises:
            ValueError: 如果同名服务已注册。

        Register a ``@service`` or ``@module`` class (idempotent).

        Args:
            cls: The service class.
            meta: Service metadata (optional).

        Raises:
            ValueError: If a service with the same name is already registered.
        """
        if cls in self._by_class:
            return

        if meta is None:
            mod_meta = get_module_meta(cls)
            meta = mod_meta if mod_meta.name else get_service_meta(cls)

        name: str = meta.name
        if name in self._by_name:
            raise ValueError(f"Service/Module '{name}' is already registered.")

        entry = ServiceEntry(
            cls=cls,
            name=name,
            deps=list(meta.deps),
            dep_names=[getattr(d, CF_NAME_ATTR, d.__name__) for d in meta.deps],
        )
        self._by_name[name] = entry
        self._by_class[cls] = entry

    def get_by_name(self, name: str) -> ServiceEntry:
        """按名称查找服务。

        Args:
            name: 服务名称。

        Returns:
            服务条目。

        Raises:
            ServiceNotFoundError: 如果服务未找到。

        Look up a service by name.

        Args:
            name: The service name.

        Returns:
            Service entry.

        Raises:
            ServiceNotFoundError: If the service is not found.
        """
        try:
            return self._by_name[name]
        except KeyError:
            raise ServiceNotFoundError(
                f"'{name}' is not registered. Registered: {sorted(self._by_name)}"
            ) from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        """按类查找服务。

        如果在当前注册表中找不到，会查找父注册表。

        Args:
            cls: 服务类。

        Returns:
            服务条目。

        Raises:
            ServiceNotFoundError: 如果服务未找到。

        Look up a service by class.

        Searches the parent registry if not found in the current registry.

        Args:
            cls: The service class.

        Returns:
            Service entry.

        Raises:
            ServiceNotFoundError: If the service is not found.
        """
        current: Registry | None = self
        while current is not None:
            try:
                return current._by_class[cls]
            except KeyError:
                current = current.parent
        raise ServiceNotFoundError(f"'{cls.__name__}' is not registered.") from None

    def get_instance(self, cls: type) -> object:
        """获取服务实例。

        Args:
            cls: 服务类。

        Returns:
            服务实例。

        Raises:
            ServiceNotFoundError: 如果服务未找到。

        Get the service instance.

        Args:
            cls: The service class.

        Returns:
            Service instance.

        Raises:
            ServiceNotFoundError: If the service is not found.
        """
        return self.get_by_class(cls).instance

    def has(self, cls: type) -> bool:
        """检查服务是否已注册。

        Args:
            cls: 服务类。

        Returns:
            如果服务已注册则返回True，否则返回False。

        Check if a service is registered.

        Args:
            cls: The service class.

        Returns:
            True if the service is registered, False otherwise.
        """
        current: Registry | None = self
        while current is not None:
            if cls in current._by_class:
                return True
            current = current.parent
        return False

    def all_entries(self) -> list[ServiceEntry]:
        """获取所有服务条目。

        Returns:
            当前注册表中的所有服务条目列表。

        Get all service entries.

        Returns:
            List of all service entries in the current registry.
        """
        return list(self._by_name.values())

    def names(self) -> list[str]:
        """获取所有服务名称。

        Returns:
            当前注册表中的所有服务名称列表。

        Get all service names.

        Returns:
            List of all service names in the current registry.
        """
        return list(self._by_name.keys())

    def __len__(self) -> int:
        """返回注册表中的服务数量。

        Returns:
            服务数量。

        Return the number of services in the registry.

        Returns:
            Number of services.
        """
        return len(self._by_name)

    def __contains__(self, cls: type) -> bool:
        """检查服务是否在注册表中。

        Args:
            cls: 服务类。

        Returns:
            如果服务在注册表中则返回True，否则返回False。

        Check if a service is in the registry.

        Args:
            cls: The service class.

        Returns:
            True if the service is in the registry, False otherwise.
        """
        return self.has(cls)

    def __iter__(self) -> Iterator[ServiceEntry]:
        """返回服务条目的迭代器。

        Returns:
            服务条目迭代器。

        Return an iterator over service entries.

        Returns:
            Iterator over service entries.
        """
        return iter(self._by_name.values())


__all__ = ["Registry"]
