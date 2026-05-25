"""CF 框架核心引擎 —— 生命周期编排器。

负责服务的递归发现、依赖校验、拓扑排序、Context 树构建和生命周期钩子调度。
通过 Canary 和 WebCanary 两个公开类暴露给用户。

日志系统:
    框架使用 "cf" 命名空间的 logger，通过 CF_LOG_LEVEL 环境变量控制级别（默认 INFO）。
    日志格式: [CF] [LEVEL] [module] message
    与 uvicorn 日志隔离（不同的 logger 名称），不会重复输出。
"""

from __future__ import annotations

import asyncio
import logging
import os

from cf.core.decorators.lifecycle import find_hooks
from cf.core.decorators.module import get_module_meta, is_cf_module
from cf.core.decorators.service import get_service_meta, is_cf_service
from cf.core.engine.context import Context
from cf.core.engine.injector import inject_deps
from cf.core.engine.sorter import topological_sort
from cf.core.registry.registry import Registry, ServiceEntry

# 框架日志系统
# 格式 [CF] [LEVEL] [模块] 消息，与 uvicorn 的 root logger 完全隔离（cf 命名空间）
_cf_logger = logging.getLogger("cf")


def _init_logging() -> None:
    """初始化框架日志：从 CF_LOG_LEVEL 环境变量读取级别，配置格式和 handler。

    只会配置一次（幂等），避免重复添加 handler。
    logger.propagate = False 确保日志不传播到 root logger，不与 uvicorn 冲突。
    """
    level_name = os.environ.get("CF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    _cf_logger.setLevel(level)

    # 幂等：已经配置过 handler 则跳过
    if _cf_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[CF] [%(levelname)-5s] [%(name)s] %(message)s"))
    _cf_logger.addHandler(handler)
    # 禁止向 root logger 传播，避免 uvicorn 或其他库的 root handler 重复打印
    _cf_logger.propagate = False

    _cf_logger.debug("Logging initialized at level=%s", level_name)


def _get_logger(name: str) -> logging.Logger:
    """获取 cf 命名空间下的子 logger，如 cf.engine、cf.di、cf.config。"""
    return logging.getLogger(f"cf.{name}")


class Canary:
    """Canary 核心引擎 —— 服务生命周期编排器。

    负责完整的应用生命周期:
        init()  → 收集 → 校验 → 拓扑排序 → Context 树 → DI → 配置 → on_init
        start() → 按拓扑序触发 on_start
        stop()  → 按逆序触发 on_end

    Usage:
        app = Canary(MyRootModule)
        await app.init()
        await app.start()
        await app.stop()
    """

    def __init__(self, target: type) -> None:
        self._target = target  # 根模块/服务类（入口点）
        self._registry = Registry()  # 全局注册中心
        self._startup_order: list[str] = []  # 拓扑排序后的名称列表

    @property
    def registry(self) -> Registry:
        """公开 Registry，供子类（WebCanary）和测试访问。"""
        return self._registry

    # ── 公开生命周期方法 ─────────────────────────────────

    async def init(self) -> None:
        """初始化阶段：收集服务、校验依赖、构建 Context、注入、加载配置、调 on_init。

        四阶段流程:
            0. _collect()      — 递归发现并注册所有 @service / @module 类
            1. _validate()     — 校验 deps 中声明的依赖完整性
            2. topological_sort() — Kahn 算法计算启动顺序
            3. _build_context_tree() — 按模块树建立 Context parent 链
            4. 按拓扑序: 依赖注入 → 配置加载 → on_init(ctx)
        """
        _init_logging()
        engine = _get_logger("engine")
        engine.info("── init start ──")

        # ── 阶段0: 收集 ──
        engine.debug("Phase 0: collecting services/modules")
        self._collect(self._target)

        # ── 阶段1: 校验 ──
        engine.debug("Phase 1: validating dependencies")
        self._validate()

        # ── 阶段2: 拓扑排序 ──
        engine.debug("Phase 2: topological sort")
        self._startup_order = topological_sort(self._registry)
        engine.info(
            "Startup order (%d): %s", len(self._startup_order), " → ".join(self._startup_order)
        )

        # ── 阶段3: 构建 Context 链 ──
        engine.debug("Phase 3: building context tree")
        self._build_context_tree(self._target, parent_ctx=None)

        # ── 阶段4: 逐个初始化 ──
        engine.debug("Phase 4: initializing entries")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._init_entry(entry)

        engine.info("── init complete (%d services) ──", len(self._startup_order))

    async def start(self) -> None:
        """启动阶段：按拓扑序触发所有服务的 on_start 钩子。"""
        engine = _get_logger("engine")
        engine.info("── start ──")
        for name in self._startup_order:
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, "on_start")
        engine.info("── start complete ──")

    async def stop(self) -> None:
        """停止阶段：按逆序触发所有服务的 on_end 钩子。"""
        engine = _get_logger("engine")
        engine.info("── stop ──")
        for name in reversed(self._startup_order):
            entry = self._registry.get_by_name(name)
            await self._call_hook(entry, "on_end")
        engine.info("── stop complete ──")

    # ── _init_entry: 单个 entry 的初始化 ──────────────────

    async def _init_entry(self, entry: ServiceEntry) -> None:
        """对单个注册项执行: 依赖注入 → 配置加载 → 触发 on_init 钩子。"""
        engine = _get_logger("engine")
        config_log = _get_logger("config")

        engine.info("  init %s", entry.name)

        # 依赖注入
        inject_deps(entry.instance, entry, self._registry)

        # 配置加载
        if entry.config_cls is not None:
            entry.config_instance = entry.config_cls()
            config_log.info(
                "  %s config loaded: %s",
                entry.name,
                {k: v for k, v in vars(entry.config_instance).items() if not k.startswith("_")},
            )
        else:
            config_log.debug("  %s has no config", entry.name)

        # on_init 钩子
        await self._call_hook(entry, "on_init", entry.context)

    # ── _call_hook ─────────────────────────────────────────

    @staticmethod
    async def _call_hook(entry: ServiceEntry, hook_name: str, *args: object) -> None:
        """统一钩子调用（sync / async 自动适配）。

        钩子查找结果缓存在 entry._hooks 上，每个 entry 仅扫描一次 dir(instance)。
        asyncio.iscoroutine 判断方法返回值是否为协程，是则 await。
        """
        lifecycle = _get_logger("lifecycle")
        if entry._hooks is None:
            entry._hooks = find_hooks(entry.instance)
        fn = entry._hooks.get(hook_name)
        if fn is None:
            lifecycle.debug("  %s.%s: not defined", entry.name, hook_name)
            return
        lifecycle.info("  %s.%s()", entry.name, hook_name)
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result

    # ── _collect ─────────────────────────────────────────

    def _collect(
        self,
        cls: type,
        parent_entry: ServiceEntry | None = None,
    ) -> None:
        """递归收集 @service / @module 类，注册到 Registry，建立父子关系。

        对于模块，递归处理其 services 列表中的子节点。
        对于服务，仅注册自身。
        config_cls 继承: 子节点未声明 config → 从父模块拷贝。
        """
        if self._registry.has(cls):
            return

        registry_log = _get_logger("registry")

        # 分支：模块
        if is_cf_module(cls):
            meta = get_module_meta(cls)
            self._registry.register(cls, is_module=True, meta=meta)
            entry = self._registry.get_by_class(cls)
            entry.parent_entry = parent_entry
            self._inherit_config(entry, parent_entry)

            registry_log.info(
                "  module %-30s config=%s  services=%d",
                entry.name,
                entry.config_cls.__name__ if entry.config_cls else "inherit",
                len(meta.get("services", [])),
            )
            for sub_cls in meta.get("services", []):
                self._collect(sub_cls, parent_entry=entry)
            return

        # 分支：服务
        if is_cf_service(cls):
            meta = get_service_meta(cls)
            self._registry.register(cls, is_module=False, meta=meta)
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

        raise TypeError(f"'{cls.__name__}' is not decorated with @service or @module")

    def _inherit_config(self, entry: ServiceEntry, parent_entry: ServiceEntry | None) -> None:
        """子节点未声明 config_cls 时，从父模块拷贝。"""
        if entry.config_cls is None and parent_entry is not None:
            entry.config_cls = parent_entry.config_cls

    # ── _build_context_tree ──────────────────────────────

    def _build_context_tree(
        self,
        cls: type,
        parent_ctx: Context | None,
    ) -> None:
        """按模块树递归构建 Context parent 链。

        每个 ServiceEntry 绑定一个 Context，根模块的 parent 为 None。
        子服务的 parent 指向所属模块的 Context。
        """
        entry = self._registry.get_by_class(cls)
        ctx = Context(entry=entry, parent=parent_ctx, registry=self._registry)
        entry.context = ctx

        if entry.is_module:
            for sub_cls in entry.sub_services:
                self._build_context_tree(sub_cls, parent_ctx=ctx)

    # ── _validate ────────────────────────────────────────

    def _validate(self) -> None:
        """校验所有 deps 中声明的依赖是否都已注册。

        遍历所有 ServiceEntry，检查 dep_names 中的每个名称是否在 Registry 中存在。
        不存在时抛出 ValueError 并列出所有已注册名称。
        """
        all_names = set(self._registry.names())
        for entry in self._registry.all_entries():
            for dep_name in entry.dep_names:
                if dep_name not in all_names:
                    raise ValueError(
                        f"Service '{entry.name}' depends on '{dep_name}', "
                        f"but '{dep_name}' is not registered. "
                        f"Registered: {sorted(all_names)}"
                    )
