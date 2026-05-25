"""Framework-wide shared type definitions.

命名约定 (Naming convention):
    ``_types.py`` 以下划线开头，表明它是框架内部模块，不直接暴露给用户。
    The leading underscore signals this is an internal module, not a
    public API surface.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from canary_framework.core.conductor.context import Context


# ============================================================================
# TypedDict 元数据 — 装饰器在类上设置的元数据
# TypedDict metadata — stored on decorated classes by @service / @module
# ============================================================================


class ServiceMeta(TypedDict, total=False):
    """Metadata stored on a ``@service``-decorated class.

    存储服务声明时的元信息，在注册阶段由 Registry 消费。
    The dict is created at decoration time and consumed by :class:`Registry`
    during collection.

    所有字段都是 ``total=False``，因为 TypedDict 在构造时一次性填充，
    之后不会再修改。
    All keys are ``total=False`` because the dict is populated once at
    decoration time and never mutated afterwards.
    """

    name: str
    """Globally unique service name, e.g. ``"db"``."""

    deps: list[type]
    """List of ``@service`` / ``@module`` classes this service depends on."""

    config_cls: type | None
    """Optional ``@config``-decorated class.  ``None`` means inherit from parent."""


class ModuleMeta(TypedDict, total=False):
    """Metadata stored on a ``@module``-decorated class.

    模块元数据格式与 ServiceMeta 类似，额外包含 ``services`` 子节点列表。
    模块本身也是服务，因此也支持配置和依赖注入。
    A module is itself a service, so it carries the same shape as
    :class:`ServiceMeta` with an additional ``services`` list.
    """

    name: str
    """Globally unique module name."""

    config_cls: type | None
    """Optional ``@config``-decorated class.  Child services inherit this
    when they don't declare their own."""

    services: list[type]
    """List of direct child ``@service`` / ``@module`` classes."""


# ============================================================================
# ServiceEntry — 单个服务/模块的完整运行时状态
# ServiceEntry — full runtime descriptor for one service or module
# ============================================================================


@dataclass(slots=True)
class ServiceEntry:
    """Runtime descriptor for a single ``@service`` or ``@module`` instance.

    每个被 ``@service`` 或 ``@module`` 装饰的类在注册时生成一个 ServiceEntry。
    它在生命周期各阶段逐步被填充：收集阶段写入 cls/name/deps，初始化阶段写入
    config_instance，构建 context 树时写入 context。

    ``slots=True`` 禁用 ``__dict__``，减少内存开销。对于可能创建上百个服务
    实例的框架来说，这点至关重要。同时也防止用户误在运行时动态添加属性。

    Created during collection, progressively enriched during init/start/stop.
    ``slots=True`` disables ``__dict__`` per instance, saving memory — important
    for a framework that may create hundreds of service entries.
    """

    cls: type
    """原始用户类 (The original user class decorated with ``@service`` or ``@module``)."""

    instance: object
    """构造的实例，通过 ``cls()`` 无参构造 (Constructed via ``cls()`` with no args)."""

    name: str
    """全局唯一名称 (Globally unique name declared in the decorator)."""

    deps: list[type] = field(default_factory=list)
    """依赖类列表，用于 DI (Dependency class list from ``deps=[]``)."""

    config_cls: type | None = None
    """``@config`` 装饰的类，``None`` 时从父模块继承
    (The ``@config``-decorated class, or ``None`` to inherit from parent)."""

    is_module: bool = False
    """是否为模块 (``True`` for ``@module``, ``False`` for ``@service``)."""

    sub_services: list[type] = field(default_factory=list)
    """子服务列表，仅模块有效 (Child classes declared in ``services=[]``)."""

    dep_names: list[str] = field(default_factory=list)
    """已解析的依赖名称，供拓扑排序器使用。
    在 register 阶段从 deps 类名解析而来，而非直接从用户输入读取。
    Resolved dependency names for the topological sorter.
    Derived from *deps* during registration, not taken directly from user input."""

    config_instance: object | None = field(default=None, repr=False)
    """配置实例，在 ``_init_entry`` 中通过 ``config_cls()`` 构造。
    Pydantic-settings 会自动在此时读取 ``.env`` 和环境变量。
    Constructed in ``_init_entry`` via ``config_cls()``."""

    parent_entry: ServiceEntry | None = field(default=None, repr=False, compare=False)
    """父模块的 ServiceEntry，根模块为 ``None``。
    在 ``_collect`` 递归时记录，用于向上查找配置和构建 Context 链。
    Parent module's entry; ``None`` for root.  Set during ``_collect``."""

    context: Context | None = field(default=None, repr=False, compare=False)
    """关联的 Context，在 ``_build_context_tree`` 时绑定。
    每个 ServiceEntry 拥有独立的 Context，通过 parent 链串联。
    Assigned during ``_build_context_tree``.  Each entry gets its own
    :class:`Context`, linked via the parent chain."""

    _hooks: dict[str, Callable[..., Any]] | None = field(default=None, repr=False, compare=False)
    """缓存: ``find_hooks`` 的结果。
    延迟到首次钩子调用时填充，避免启动时对每个实例做 ``dir()`` 扫描。
    Cached result of ``find_hooks``.  Populated lazily on first hook
    invocation to avoid scanning every instance's ``dir()`` at startup."""
