"""注册中心 —— ServiceEntry 数据对象和 Registry 索引容器。

ServiceEntry: 单个服务/模块的完整元数据和运行时状态。
Registry:    管理所有 ServiceEntry，按 name 和 class 建立双向索引。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cf.core.engine.context import Context


class ServiceEntry:
    """服务/模块的注册项 —— 从装饰器提取元数据，运行时填充实例和配置。

    _collect 阶段创建（通过 Registry.register），各字段在后续阶段逐步填充:
        - parent_entry: _collect 时记录父子关系
        - context:      _build_context_tree 时创建
        - _hooks:       首次 _call_hook 时缓存 find_hooks 结果
        - config_instance: init 时通过 config_cls() 创建
        - dep_names:     register 时从 deps 类名解析
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
        self.cls = cls  # 原始类（@service 或 @module 装饰）
        self.instance = instance  # 实例（register 时 cls() 无参构造）
        self.name = name  # 名称（全局唯一）
        self.deps = deps  # 依赖服务类列表
        self.config_cls = config_cls  # 配置类（可能从父模块继承）
        self.is_module = is_module  # 是否为模块
        self.sub_services = sub_services or []  # 子服务列表（仅模块有效）
        self.dep_names: list[str] = []  # 依赖名称列表（拓扑排序用）
        self.config_instance: object | None = None  # 配置实例（init 阶段创建）
        self.parent_entry: ServiceEntry | None = None  # 父模块注册项
        self.context: Context | None = None  # 关联的 Context（构建树时绑定）
        self._hooks: dict | None = None  # 缓存: find_hooks 结果（延迟查找）


class Registry:
    """注册中心 —— 管理所有 ServiceEntry 的注册、查找和遍历。

    内部双向索引:
        _by_name:  name → ServiceEntry（名称唯一）
        _by_class: cls → ServiceEntry（类唯一）
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
        """注册一个 @service 或 @module 类。

        幂等: 如果 cls 已注册则直接返回。
        meta 为空时从类的装饰器属性中动态读取元数据。

        Args:
            cls: 被 @service 或 @module 装饰的类。
            is_module: 是否为模块。
            sub_services: 子服务列表（仅模块）。
            meta: 装饰器设置的元数据字典 {"name", "deps", "config_cls", ...}。
        """
        if cls in self._by_class:
            return

        if meta is None:
            from cf.core.decorators.module import get_module_meta
            from cf.core.decorators.service import get_service_meta

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

        # 将 deps 中的类引用转换为字符串名称
        entry.dep_names = [
            d if isinstance(d, str) else getattr(d, "__cf_name__", d.__name__) for d in entry.deps
        ]

        self._by_name[name] = entry
        self._by_class[cls] = entry

    # ── 查询方法 ──────────────────────────────────────────

    def get_by_name(self, name: str) -> ServiceEntry:
        """按名称查找注册项。"""
        return self._by_name[name]

    def get_by_class(self, cls: type) -> ServiceEntry:
        """按类对象查找注册项。"""
        return self._by_class[cls]

    def get_instance(self, cls: type) -> object:
        """获取类的运行时实例。"""
        return self._by_class[cls].instance

    def has(self, cls: type) -> bool:
        """判断某类是否已注册。"""
        return cls in self._by_class

    def all_entries(self) -> list[ServiceEntry]:
        """返回所有注册项列表。"""
        return list(self._by_name.values())

    def names(self) -> list[str]:
        """返回所有已注册名称列表。"""
        return list(self._by_name.keys())
