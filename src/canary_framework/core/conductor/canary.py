"""Core engine — life-cycle orchestrator for services and modules.

设计思路 (Design rationale):
    为什么叫 Canary（金丝雀）？
    （Why "Canary"?）

    金丝雀在煤矿中作为早期预警系统——框架同样用于「检测」和「编排」服务。
    类比：框架是矿工，服务是矿道。  The name evokes the canary in the coal
    mine — the framework "detects" and "orchestrates" services.

    为什么 init/start/stop 分为三个阶段而不是一个？
    （Why three phases — init, start, stop — instead of one?）

    1. **依赖完整性**：init 阶段结束后，所有服务的依赖链已就绪。start
       阶段保证各服务在依赖方已初始化后再开始真正的工作
       After init, all dependency chains are resolved.  start runs
       when every service can rely on its dependencies being initialised.
    2. **优雅关闭**：stop 逆序执行，先停止依赖方，再停止被依赖方
       Graceful shutdown: dependants stop first, dependencies last.
    3. **测试友好**：测试可以只调 init 验证注入和配置，无需真的启动服务
       Test-friendly: tests can call init alone to verify DI and config.

    阶段细节 (Phase details):
        =============  ======================================================
        Phase           Description
        =============  ======================================================
        ``_collect``    Recursively discover ``@service`` / ``@module`` classes
        ``_validate``   Verify all ``deps=[]`` references are registered
        ``topo sort``   Kahn's BFS — compute safe startup order
        ``_init_entry`` DI → config → ``on_init`` hook (per entry)
        =============  ======================================================

日志系统 (Logging):
    Framework uses the ``"cf"`` logger namespace (``cf.engine``,
    ``cf.di``, ``cf.config``, ``cf.lifecycle``, ``cf.registry``).
    ``propagate=False`` 确保不与 uvicorn 等库的 root logger 重复输出。
"""

from __future__ import annotations

import asyncio

from canary_framework.common._logging import get_logger, init_logging, sanitize_config_values
from canary_framework.common._types import ServiceEntry
from canary_framework.common.enums import LifecycleHook
from canary_framework.common.exceptions import LifecycleHookError
from canary_framework.core.algorithms.injector import inject_deps
from canary_framework.core.algorithms.sorter import topological_sort
from canary_framework.core.conductor.context import Context
from canary_framework.core.container.registry import Registry
from canary_framework.core.decorators.lifecycle import HookDict, find_hooks
from canary_framework.core.decorators.module import get_module_meta, is_cf_module
from canary_framework.core.decorators.service import get_service_meta, is_cf_service

# ============================================================================
# Canary — 生命周期编排器 (Lifecycle orchestrator)
# ============================================================================


class Canary:
    """Core engine — life-cycle orchestrator for the service graph.

    框架的核心引擎，负责完整的服务生命周期编排。

    使用方式 (Usage)::

        app = Canary(MyRootModule)
        await app.init()    # 收集 → 校验 → 排序 → DI → 配置 → on_init
        await app.start()   # 拓扑序调用 on_start
        # … application runs …
        await app.stop()    # 逆序调用 on_end
    """

    # __slots__ 减少内存开销，防止运行时动态添加属性
    # Reduces memory and prevents dynamic attribute assignment
    __slots__ = ("_registry", "_startup_order", "_target")

    def __init__(self, target: type) -> None:
        """Create a :class:`Canary` instance for the given root class.

        Args:
            target: 根模块或服务类（入口点）。
                    A ``@module`` or ``@service``-decorated class
                    serving as the entry point of the service graph.
        """
        self._target = target
        self._registry = Registry()
        self._startup_order: list[str] = []

    @property
    def registry(self) -> Registry:
        """The global :class:`Registry` (read-only after :meth:`init`).

        全局注册中心。init 之后只读，不应再修改。"""
        return self._registry

    @property
    def startup_order(self) -> list[str]:
        """The topological startup order computed during :meth:`init`.

        拓扑排序后的启动顺序列表。返回副本以防止外泄修改内部状态。"""
        return list(self._startup_order)

    # ==================================================================
    # 公开生命周期 (Public lifecycle)
    # ==================================================================

    async def init(self) -> None:
        """Initialize the service graph.

        Phases executed in order:
            0. ``_collect``       — recursive discovery
            1. ``_validate``      — dependency integrity check
            2. ``topological_sort`` — Kahn BFS
            3. ``_build_context_tree`` — Context parent chain
            4. Per-entry: DI → config loading → ``on_init`` hook
        """
        init_logging()
        engine = get_logger("engine")
        engine.info("── init start ──")

        # ── 阶段0: 递归收集 ──
        engine.debug("Phase 0: collecting services/modules")
        self._collect(self._target)

        # ── 阶段1: 依赖完整性校验 ──
        engine.debug("Phase 1: validating dependencies")
        self._validate()

        # ── 阶段2: 拓扑排序（Kahn BFS） ──
        engine.debug("Phase 2: topological sort")
        self._startup_order = topological_sort(self._registry)
        engine.info(
            "Startup order (%d): %s",
            len(self._startup_order),
            " → ".join(self._startup_order),
        )

        # ── 阶段3: 构建 Context 树 ──
        engine.debug("Phase 3: building context tree")
        self._build_context_tree(self._target, parent_ctx=None)

        # ── 阶段4: 按拓扑序逐个初始化 ──
        engine.debug("Phase 4: initialising entries")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._init_entry(entry)

        engine.info("── init complete (%d services) ──", len(self._startup_order))

    async def start(self) -> None:
        """Start all services in topological order.

        Calls ``on_start`` on every registered entry.
        按拓扑序触发所有服务的 on_start 钩子。"""
        engine = get_logger("engine")
        engine.info("── start ──")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.START)
        engine.info("── start complete ──")

    async def stop(self) -> None:
        """Stop all services in **reverse** topological order.

        按逆序触发所有服务的 on_end 钩子。
        依赖方先停止，被依赖方后停止。
        Calls ``on_end`` on every registered entry, starting with the
        most dependent service and ending with the least dependent.
        """
        engine = get_logger("engine")
        engine.info("── stop ──")
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, LifecycleHook.END)
        engine.info("── stop complete ──")

    # ==================================================================
    # 单个 entry 的初始化 (Entry initialisation)
    # ==================================================================

    async def _init_entry(self, entry: ServiceEntry) -> None:
        """Initialize a single service/module: DI → config → on_init.

        单个注册项的初始化流程：依赖注入 → 配置加载 → on_init 钩子。

        配置加载使用 ``config_cls()`` 无参构造。pydantic-settings 的
        ``BaseSettings.__init__`` 会自动读取 ``.env`` 和环境变量。
        """
        engine = get_logger("engine")
        config_log = get_logger("config")
        engine.info("  init %s", entry.name)

        # 1. 依赖注入：将 deps 中的服务实例 setattr 到目标实例
        inject_deps(entry.instance, entry, self._registry)

        # 2. 配置加载：config_cls() 触发 pydantic-settings 读取 .env
        if entry.config_cls is not None:
            entry.config_instance = entry.config_cls()
            raw_cfg = {
                k: v for k, v in vars(entry.config_instance).items() if not k.startswith("_")
            }
            # 日志中打印配置时自动脱敏
            config_log.info(
                "  %s config loaded: %s",
                entry.name,
                sanitize_config_values(raw_cfg),
            )
        else:
            config_log.debug("  %s has no config", entry.name)

        # 3. on_init 钩子：传入 Context
        await self._call_hook(entry, LifecycleHook.INIT, entry.context)

    # ==================================================================
    # 钩子调度 (Hook dispatch)
    # ==================================================================

    @staticmethod
    async def _call_hook(
        entry: ServiceEntry,
        hook: LifecycleHook,
        *args: object,
    ) -> None:
        """Dispatch a lifecycle hook on *entry*.

        统一钩子调度：支持同步和异步方法。

        为什么需要 ``try/except`` 包装？
        （Why wrap in try/except?）
        钩子内部的异常不能无声地吞掉，也不能让框架崩溃。包装为
        ``LifecycleHookError`` 既保留了原始异常栈，又让调用方能区分
        "钩子业务逻辑异常"和"框架内部 bug"。
        """
        lifecycle = get_logger("lifecycle")

        # 延迟加载：首次调用时扫描实例并缓存钩子
        # Lazy: scan and cache hooks on first invocation
        if entry._hooks is None:
            raw_hooks: HookDict = find_hooks(entry.instance)
            # 将 LifecycleHook 键转为字符串存入缓存
            # Convert LifecycleHook keys to strings for cache storage
            entry._hooks = {k.value: v for k, v in raw_hooks.items()}  # type: ignore[misc]

        fn_s = entry._hooks.get(hook.value)
        if fn_s is None:
            lifecycle.debug("  %s.%s: not defined", entry.name, hook.value)
            return

        lifecycle.info("  %s.%s()", entry.name, hook.value)
        try:
            result = fn_s(*args)
        except Exception as exc:
            raise LifecycleHookError(
                f"Service '{entry.name}' raised an error in {hook.value} hook: {exc}"
            ) from exc

        # 自适应: sync 或 async 钩子
        # Adaptive: detect coroutine and await if needed
        if asyncio.iscoroutine(result):
            await result

    # ==================================================================
    # 递归收集 (Recursive collection)
    # ==================================================================

    def _collect(
        self,
        cls: type,
        parent_entry: ServiceEntry | None = None,
    ) -> None:
        """Recursively discover and register ``@service`` / ``@module`` classes.

        递归收集所有被 @service / @module 装饰的类。

        收集策略 (Collection strategy):
            - 模块：注册自身 → 递归处理 services 列表中的子节点
            - 服务：注册自身 → 结束（叶子节点）
            - config 继承：子节点未声明 config_cls 时从父模块拷贝

        为什么不在 init 时一次收集？（当前实现已是一次收集）
        这个设计的关键在于：registry.register() 是幂等的，因此可以通过
        ``has()`` 检查避免重复注册，天然支持 DAG 中的共享依赖。
        """
        if self._registry.has(cls):
            return  # 已注册，幂等跳过

        registry_log = get_logger("registry")

        # ── 模块分支 ──
        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)  # type: ignore[arg-type]
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)

            registry_log.info(
                "  module %-30s config=%s  services=%d",
                entry.name,
                entry.config_cls.__name__ if entry.config_cls else "inherit",
                len(meta.get("services", ())),
            )
            # 递归：处理模块的每个子节点
            for sub_cls in meta.get("services", ()):
                self._collect(sub_cls, parent_entry=entry)
            return

        # ── 服务分支 ──
        if is_cf_service(cls):
            svc_meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=svc_meta)  # type: ignore[arg-type]
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)

            registry_log.info(
                "  service %-30s config=%s  deps=%d",
                entry.name,
                entry.config_cls.__name__ if entry.config_cls else "inherit",
                len(entry.deps),
            )
            return

        # 既不是 @service 也不是 @module —— 用户错误
        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module.")

    @staticmethod
    def _inherit_config(
        entry: ServiceEntry,
        parent_entry: ServiceEntry | None,
    ) -> None:
        """Copy *config_cls* from parent when the child has none.

        配置继承：子节点未声明 config_cls 时，从父模块拷贝。
        这是模块系统最核心的能力之一——避免在每个子服务中重复配置声明。"""
        if entry.config_cls is None and parent_entry is not None:
            entry.config_cls = parent_entry.config_cls

    # ==================================================================
    # Context 树 (Context tree construction)
    # ==================================================================

    def _build_context_tree(
        self,
        cls: type,
        parent_ctx: Context | None,
    ) -> None:
        """Build the :class:`Context` parent chain for the module tree.

        按模块树的层级关系构建 Context 父子链。

        为什么需要 parent 链？
        （Why a parent chain?）
        Context 的 ``get_config()`` 和 ``resolve()`` 都依赖向上查找。
        子服务的 Context.parent 指向所属模块的 Context，形成单向链表。
        这种设计使得每次查找都是沿链上溯，不需要维护全局映射表。

        每个 ServiceEntry 绑定一个 Context。根模块的 parent 为 None。
        """
        entry = self._registry.get_by_class(cls)
        ctx = Context(entry=entry, parent=parent_ctx, registry=self._registry)
        entry.context = ctx

        # 递归：为子模块/子服务构建 Context
        if entry.is_module:
            for sub_cls in entry.sub_services:
                self._build_context_tree(sub_cls, parent_ctx=ctx)

    # ==================================================================
    # 依赖校验 (Dependency validation)
    # ==================================================================

    def _validate(self) -> None:
        """Verify every ``deps=[]`` reference corresponds to a registered entry.

        校验所有 deps 中声明的依赖是否都已注册。

        为什么不在 _collect 阶段校验？
        （Why validate after collection instead of during?）
        在收集完成后再校验可以确保所有服务都已注册，避免因收集顺序
        导致的误报。此时 Registry 的状态是完整且一致的。
        """
        all_names = set(self._registry.names())
        for entry in self._registry.all_entries():
            for dep_name in entry.dep_names:
                if dep_name not in all_names:
                    registered = sorted(all_names) if all_names else ["(none)"]
                    raise ValueError(
                        f"Service '{entry.name}' depends on '{dep_name}', "
                        f"but '{dep_name}' is not registered. "
                        f"Registered names: {registered}"
                    )
