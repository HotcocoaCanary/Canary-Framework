"""Container — central registry of all registered services and modules.

设计思路 (Design rationale):
    为什么 Registry 不使用线程锁？
    （Why no thread-safety in Registry?）

    Registry 的写入只发生在 ``Canary.init()`` 阶段（单线程收集），
    之后在所有阶段中只读。这种「单写多读」模式不需要锁，且避免了
    每次查询的性能开销。

    未来如果支持「运行时热注册」，则需要引入 ``threading.RLock``。

    为什么需要双向索引（``_by_name`` + ``_by_class``）？
    （Why dual indexes — by-name and by-class?）
    拓扑排序按名称查找，DI 注入按类对象查找。两个独立的字典提供 O(1)
    查询性能，避免了遍历列表的 O(n) 开销。
"""

from __future__ import annotations

from collections.abc import Iterator

from canary_framework.common._types import ModuleMeta, ServiceEntry, ServiceMeta
from canary_framework.common.exceptions import ServiceNotFoundError


class Registry:
    """Central registry — O(1) lookup by name or class.

    全局注册中心，通过名称和类对象的双向索引提供 O(1) 查找。
    在 ``_collect`` 阶段填充后保持只读。"""

    def __init__(self) -> None:
        # 双向索引：名称 → Entry，类 → Entry
        # Dual indexes: name → Entry, class → Entry
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    # ==================================================================
    # 注册 (Registration)
    # ==================================================================

    def register(
        self,
        cls: type,
        *,
        meta: ServiceMeta | None = None,
    ) -> None:
        """Register a ``@service`` or ``@module`` class.

        注册一个 ``@service`` 或 ``@module`` 类。

        幂等 (Idempotent): 如果 *cls* 已注册则直接返回。
        这简化了递归收集逻辑——不同模块可以包含同一个服务，不会重复注册。

        Args:
            cls: 被 ``@service`` 或 ``@module`` 装饰的类。
            meta: 预解析的元数据实例，为 ``None`` 时从类的装饰器属性读取。
        """
        if cls in self._by_class:
            return

        # 解析元数据：未提供时从类的装饰器属性读取
        if meta is None:
            from canary_framework.core.decorators.service import get_service_meta

            meta = get_service_meta(cls)

        name: str = meta.name
        if name in self._by_name:
            raise ValueError(
                f"Service/Module '{name}' is already registered. "
                f"Each @service and @module must have a globally unique name."
            )

        instance = cls()

        entry = ServiceEntry(
            cls=cls,
            instance=instance,
            name=name,
            deps=list(meta.deps),
            sub_services=list(meta.services if isinstance(meta, ModuleMeta) else []),
        )

        # 将 deps 中的类引用解析为字符串名称，供拓扑排序使用
        entry.dep_names = [getattr(d, "__cf_name__", d.__name__) for d in entry.deps]

        self._by_name[name] = entry
        self._by_class[cls] = entry

    # ==================================================================
    # 查询 (Lookup)
    # ==================================================================

    def get_by_name(self, name: str) -> ServiceEntry:
        """Look up a registered entry by its unique name.

        按名称查找。Registry 中每个 service/module 名称全局唯一。

        Raises:
            ServiceNotFoundError: 名称未注册。"""
        try:
            return self._by_name[name]
        except KeyError:
            raise ServiceNotFoundError(
                f"'{name}' is not registered. Registered names: {sorted(self._by_name)}"
            ) from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        """Look up a registered entry by its original class object.

        按类对象查找。

        Raises:
            ServiceNotFoundError: 类未注册。"""
        try:
            return self._by_class[cls]
        except KeyError:
            raise ServiceNotFoundError(f"'{cls.__name__}' is not registered.") from None

    def get_instance(self, cls: type) -> object:
        """Return the runtime instance for the given class.

        获取类的运行时实例。相当于 ``get_by_class(cls).instance``。

        Raises:
            ServiceNotFoundError: 类未注册。"""
        return self.get_by_class(cls).instance

    def has(self, cls: type) -> bool:
        """Return ``True`` if *cls* is registered.

        判断类是否已注册（O(1)）。"""
        return cls in self._by_class

    # ==================================================================
    # 遍历 (Iteration)
    # ==================================================================

    def all_entries(self) -> list[ServiceEntry]:
        """Return all registered entries (no guaranteed order).

        返回所有注册项列表。无顺序保证。"""
        return list(self._by_name.values())

    def names(self) -> list[str]:
        """Return the names of all registered entries.

        返回所有已注册名称列表。"""
        return list(self._by_name.keys())

    def __len__(self) -> int:
        """Number of registered entries. 已注册数。"""
        return len(self._by_name)

    def __contains__(self, cls: type) -> bool:
        """Check if *cls* is registered. 等价于 ``has()``。"""
        return cls in self._by_class

    def __iter__(self) -> Iterator[ServiceEntry]:
        """Iterate over all registered :class:`ServiceEntry` objects.

        遍历所有注册项。"""
        return iter(self._by_name.values())
