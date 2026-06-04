"""服务注册表实现。

提供服务注册、查找和迭代功能，支持父子注册表继承。

Registry writes happen only during ``configure`` (single-threaded),
after which it is read-only. No thread-safety needed for the
"write-once, read-many" pattern.

Service registry implementation.

Provides service registration, lookup, and iteration with parent-child inheritance.
"""

from __future__ import annotations

from canary_framework.common import (
    ServiceEntry,
    ServiceMeta,
    ServiceNotFoundError,
)
from canary_framework.engine.logging import get_logger

_log = get_logger("registry")


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

    def register(self, cls: type, *, meta: ServiceMeta) -> None:
        """注册一个服务（幂等操作）。

        如果类已注册，则跳过。

        Args:
            cls: 服务类。
            meta: 服务元数据。

        Raises:
            ValueError: 如果同名服务已注册。

        Register a ``@service`` or ``@module`` class (idempotent).

        Args:
            cls: The service class.
            meta: Service metadata.

        Raises:
            ValueError: If a service with the same name is already registered.
        """
        if cls in self._by_class:
            return

        name: str = meta.name
        if name in self._by_name:
            raise ValueError(f"Service/Module '{name}' is already registered.")

        entry = ServiceEntry(cls=cls, name=name)
        self._by_name[name] = entry
        self._by_class[cls] = entry
        _log.debug("Registered service/module: %s -> %s", cls.__name__, name)

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


__all__ = ["Registry"]
