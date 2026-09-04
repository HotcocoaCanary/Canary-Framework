"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，
让“嵌套”“单独启动”“组合”共用同一条代码路径。引擎是 async 原生：钩子既可以是
同步函数，也可以是协程函数，运行时按返回值自动判断是否 ``await``。

``Canary`` 本身也是一个 ASGI 应用：``__call__`` 处理 lifespan 驱动生命周期，并把
http/websocket 等 scope 委托给所有 ``@web_cocoa`` 单元合并后的统一服务入口。
"""

from __future__ import annotations

import inspect
import logging
import types
from collections.abc import Callable, Mapping
from typing import Any, Literal, Self, TypeVar, cast

from canary_framework.common.config import CanaryConfig, is_config
from canary_framework.common.error import InjectionError, LifecycleError, OverrideError
from canary_framework.common.markers import ERROR_ENTRIES_ATTR, ROUTE_ENTRIES_ATTR, WEB_ATTR
from canary_framework.common.type import LifecycleState, Receive, Scope, Send
from canary_framework.core.decorator.introspect import (
    annotations_of,
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)
from canary_framework.core.infra.naming import to_snake
from canary_framework.runtime.graph import build_graph, topological_sort
from canary_framework.runtime.mounts import join_path, mount_prefixes

_log = logging.getLogger("canary.runtime")


def _apply_framework_config() -> None:
    """Apply ``CANARY_*`` settings — currently just the level of the ``canary`` logger tree.

    只动 ``canary`` 这一棵 logger 的级别：不装 handler、不设 format、不碰 root。
    未设置 ``CANARY_LOG_LEVEL`` 时框架完全不干预，行为与标准库一致。
    """
    level = CanaryConfig().log_level
    if level:
        logging.getLogger("canary").setLevel(level.upper())


_T = TypeVar("_T")

# 一个钩子：同步时返回 None，异步时返回一个可等待对象（协程）。
# ``Callable[[], object]`` 对二者都成立——协程也是 ``object`` 的子类型。
_Hook = Callable[[], object]

# 路由条目：(method, path, instance, handler)
_RouteEntry = tuple[str, str, object, Callable[..., object]]

# 异常映射条目：(exception type, handler)
_ErrorEntry = tuple[type[Exception], Callable[..., object]]

# 进行中的状态：只可能被并发调用者观察到，此时再驱动生命周期一定是误用。
_TRANSIENT = (
    LifecycleState.INITIALIZING,
    LifecycleState.STARTING,
    LifecycleState.STOPPING,
)


class Canary:
    """A runtime that owns a graph of cocoas and drives their lifecycle.

    编排器：解析依赖图、按拓扑序驱动 ``init`` / ``start`` / ``stop``。
    异步原生——同步钩子直接调用，异步钩子自动 ``await``。带服务单元时，``Canary``
    自身就是 ASGI 应用，可直接 ``uvicorn app:app``。
    """

    def __init__(self, *roots: type, overrides: Mapping[type, object] | None = None) -> None:
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        self.roots = roots
        # 依赖替身：类型 -> 现成实例。测试里把仓储/模型换成假的，无需在业务代码里
        # 留配置开关。见 :func:`~canary_framework.runtime.graph.build_graph`。
        self._overrides: Mapping[type, object] = overrides or {}
        self._state = LifecycleState.NEW
        self._graph: dict[type, object] = {}
        self._order: list[type] = []
        self._serve_app: Any | None = None
        # 配置实例按类型共享：同一份配置类被多个单元声明时只构造一次。
        self._configs: dict[type, object] = {}
        self._route_entries: list[_RouteEntry] = []
        self._error_entries: list[_ErrorEntry] = []
        # 已进入 ``@on_start`` 的单元，按进入顺序；回收时逆序消费。
        # 记录的是“进入”而非“完成”——启动到一半失败的单元同样要被回收。
        self._started: list[type] = []

    # -- read access --------------------------------------------------
    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def order(self) -> tuple[type, ...]:
        """The topological startup order (dependencies first).

        拓扑启动顺序（依赖在前）。
        """
        return tuple(self._order)

    @property
    def instances(self) -> tuple[object, ...]:
        """The instances, in topological order.

        按拓扑序排列的实例元组。
        """
        return tuple(self._graph[t] for t in self._order)

    def __getitem__(self, cls: type[_T]) -> _T:
        """Return the shared singleton registered for *cls*.

        返回 ``cls`` 对应的共享单例。
        """
        return cast(_T, self._graph[cls])

    # -- lifecycle ----------------------------------------------------
    async def init(self) -> None:
        """``NEW -> INITIALIZED``: build the graph and run ``@on_init`` in order.

        建图 + 拓扑排序，按序执行 ``@on_init``。
        """
        self._require(LifecycleState.NEW)
        self._state = LifecycleState.INITIALIZING
        try:
            _apply_framework_config()
            self._graph = build_graph(list(self.roots), self._overrides)
            self._order = topological_sort(self._graph)
            for t in self._order:
                for hook in init_hooks(self._graph[t]):
                    await self._invoke_hook(hook)
        except Exception:
            self._state = LifecycleState.FAILED
            raise
        self._state = LifecycleState.INITIALIZED

    async def start(self) -> None:
        """``INITIALIZED -> STARTED``: inject deps, run ``@on_start``, collect serve app.

        注入依赖（懒注入），按序执行 ``@on_start``，随后收集所有 ``@web_cocoa``
        单元的路由并合并为统一的服务入口。

        不变式：**要么全部启动，要么什么都没启动。** 任一环节抛出时，已进入
        ``@on_start`` 的单元（含失败的那一个）会按逆序执行 ``@on_stop`` 回收，
        随后原样抛出最初的异常；回收过程中的异常作为 note 附在其上，不改变异常类型。
        """
        self._require(LifecycleState.INITIALIZED)
        self._state = LifecycleState.STARTING
        try:
            for t in self._order:
                node = self._graph[t]
                self._inject(node)
                self._started.append(t)
                for hook in start_hooks(node):
                    await self._invoke_hook(hook)
            self._require_overrides_applied()
            self._serve_app = self._collect_serve_app()
        except Exception as exc:
            self._state = LifecycleState.FAILED
            for err in await self._unwind():
                exc.add_note(f"during rollback: {err!r}")
            raise
        self._state = LifecycleState.STARTED
        if _log.isEnabledFor(logging.DEBUG):
            # 诊断绝不能反过来弄坏应用：摘要出问题就只报摘要出了问题。
            try:
                _log.debug("%s", self._assembly_summary())
            except Exception:  # pragma: no cover - 仅防御
                _log.debug("assembly summary unavailable", exc_info=True)

    async def stop(self) -> None:
        """Reclaim everything that was started, in reverse order.

        按台账逆序执行 ``@on_stop``。它是**唯一的回收路径**，同时承接正常结束与失败
        结束：从 ``STARTED`` 可调，从 ``FAILED`` 也可调，重复调用是幂等的。

        单个 ``@on_stop`` 抛出不会中断回收——异常被逐一收集，其余单元照常回收，
        最后合并成一个 :exc:`ExceptionGroup` 抛出（哪怕只有一个）。
        """
        if self._state in _TRANSIENT:
            raise LifecycleError(f"Canary: stop() is illegal while {self._state.name}")
        if not self._started:
            # 没起来过、或已经收干净了：空转，但不抹掉先前的失败。
            if self._state is not LifecycleState.FAILED:
                self._state = LifecycleState.STOPPED
            return
        self._state = LifecycleState.STOPPING
        errors = await self._unwind()
        if errors:
            self._state = LifecycleState.FAILED
            raise ExceptionGroup(f"Canary: {len(errors)} error(s) while stopping", errors)
        self._state = LifecycleState.STOPPED

    # -- ASGI ---------------------------------------------------------
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve ASGI: lifespan drives the lifecycle, everything else delegates.

        ``lifespan`` 交给 :meth:`_lifespan`；其余 scope（http/websocket/…）在确保已
        启动后委托给合并出的统一服务入口。
        """
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        if self.state is LifecycleState.NEW:
            await self._ensure_started()
        if self._serve_app is None:
            raise RuntimeError(f"Canary has no serving app for scope type {scope['type']!r}")
        await self._serve_app(scope, receive, send)

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await self._ensure_started()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as exc:
                    # 启动失败即宣告 lifespan 结束：服务器不会再发 shutdown，
                    # 继续 await receive() 会让调用方（如 TestClient）一直挂着。
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
            elif message["type"] == "lifespan.shutdown":
                try:
                    await self.stop()
                finally:
                    await send({"type": "lifespan.shutdown.complete"})
                return

    async def _ensure_started(self) -> None:
        if self.state is LifecycleState.NEW:
            await self.init()
            await self.start()

    def _collect_serve_app(self) -> Any | None:
        """Collect the units' route entries and merge them into one serving app.

        每个 ``@web_cocoa`` 单元在 ``@on_start`` 里把自己的路由条目写到
        ``ROUTE_ENTRIES_ATTR``；这里按 :func:`~canary_framework.runtime.mounts.mount_prefixes`
        算出的挂载前缀拼出完整路径，再交给 web 扩展合并成一个统一的应用（含
        ``/openapi.json``、``/docs``、``/redoc``）。

        前缀沿依赖链嵌套——``prefix="/api"`` 的单元依赖 ``prefix="/admin"`` 的单元时，
        后者的路由挂到 ``/api/admin`` 之下；被多条依赖路径引用时，实例仍只有一个，但
        每条路径各挂一份。只有一个 ``@web_cocoa`` 时与旧版行为一致。

        对 web 扩展的 import 是延迟的：没有路由条目就不会发生，纯 ``@cocoa`` 编排
        因此无需安装 ``canary-framework[web]``。
        """
        all_entries: list[_RouteEntry] = []
        all_error_entries: list[_ErrorEntry] = []
        meta: dict[str, str] = {}  # 文档元数据取最外层单元的

        # mount_prefixes 按“根在前”的顺序返回，故最外层单元的 title/version 胜出
        for cls, prefixes in mount_prefixes(self.roots, self._graph).items():
            node = self._graph[cls]
            # 异常映射的作用域是全应用，与挂载点无关，因此每个单元只收一次。
            all_error_entries.extend(getattr(node, ERROR_ENTRIES_ATTR, None) or [])
            entries: list[_RouteEntry] | None = getattr(node, ROUTE_ENTRIES_ATTR, None)
            if entries is None:
                continue
            for prefix in prefixes:
                all_entries.extend(
                    (m, join_path(prefix, p), inst, fn) for m, p, inst, fn in entries
                )
            meta = meta or getattr(cls, WEB_ATTR, {})

        self._route_entries = all_entries
        self._error_entries = all_error_entries
        if not all_entries:
            return None
        from canary_framework.web.core.app import build_serve_app

        return build_serve_app(meta, all_entries, all_error_entries)

    # -- context manager ----------------------------------------------
    async def __aenter__(self) -> Self:
        await self.init()
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> Literal[False]:
        await self.stop()
        return False

    # -- internals ----------------------------------------------------
    def _inject(self, node: object) -> None:
        """Fill a unit's declared collaborators: dependencies, its logger, its config.

        三个来源，同一条规则——**声明什么就填什么**：

        - ``@cocoa(deps=[Database])`` → ``node.database``（类名的 snake_case）；
        - 类级注解 ``log: Logger`` → 以 ``模块.类名`` 命名的 logger；
        - 类级注解 ``config: RepoConfig`` → 该配置类的共享实例。

        两个来源抢同一个属性名时抛 :class:`InjectionError`，不再"后写的赢"。
        """
        cls = type(node)
        plan: dict[str, tuple[str, object]] = {}

        def claim(name: str, claimant: str, value: object) -> None:
            if name in plan:
                raise InjectionError(cls.__name__, name, [plan[name][0], claimant])
            plan[name] = (claimant, value)

        for dep in deps_of(cls):
            claim(to_snake(dep.__name__), f"dependency {dep.__name__}", self._graph[dep])
        for name, annotation in annotations_of(cls).items():
            if annotation is logging.Logger:
                claim(
                    name,
                    "annotation Logger",
                    logging.getLogger(f"{cls.__module__}.{cls.__qualname__}"),
                )
            elif is_config(annotation):
                claim(name, f"annotation {annotation.__name__}", self._config_for(annotation))

        for name, (_claimant, value) in plan.items():
            setattr(node, name, value)

    def _require_overrides_applied(self) -> None:
        """Every override must have replaced something; a typo must not pass silently."""
        unused = [
            t.__name__ for t in self._overrides if t not in self._graph and t not in self._configs
        ]
        if unused:
            raise OverrideError(unused)

    def _config_for(self, config_type: type) -> object:
        """Return the shared instance of *config_type*, honouring ``overrides``.

        配置实例走和依赖单元同一套替换机制：``overrides={RepoConfig: RepoConfig(...)}``。
        """
        if config_type not in self._configs:
            if config_type in self._overrides:
                self._configs[config_type] = self._overrides[config_type]
            else:
                self._configs[config_type] = config_type()
        return self._configs[config_type]

    def _assembly_summary(self) -> str:
        """Render what the runtime actually assembled — the graph knows, so it should say.

        装配摘要：框架掌握着全部事实（顺序、依赖、替身、挂载、路由、异常映射），
        却一直零输出。这里在 DEBUG 级别一次性说清楚，排查"为什么这条路由不在"
        或"为什么这个单元先启动"时不必再去读框架源码。
        """
        lines = [f"Canary assembled {len(self._order)} unit(s)"]
        lines.append("  roots: " + ", ".join(r.__name__ for r in self.roots))
        if len(self.roots) > 1:
            lines.append(
                "  note: with multiple roots no unit starts last, so there is no "
                "'after everything started' position; declare one composition root if you need it"
            )
        lines.append("  start order (stop runs in reverse):")
        for i, t in enumerate(self._order, 1):
            # 用实例的类型而非声明类型取依赖——替身没有依赖，展示要和实际注入一致。
            deps = ", ".join(d.__name__ for d in deps_of(type(self._graph[t])))
            substituted = " [overridden]" if t in self._overrides else ""
            lines.append(f"    {i}. {t.__name__}{substituted}" + (f"  <- {deps}" if deps else ""))
        if self._route_entries:
            lines.append("  routes:")
            for method, path, instance, fn in self._route_entries:
                lines.append(
                    f"    {method:<6} {path}  -> {type(instance).__name__}."
                    f"{getattr(fn, '__name__', fn)}"
                )
        if self._error_entries:
            lines.append("  error handlers:")
            for exc_type, fn in self._error_entries:
                lines.append(f"    {exc_type.__name__} -> {getattr(fn, '__qualname__', fn)}")
        return "\n".join(lines)

    async def _unwind(self) -> list[Exception]:
        """Drain the ledger in reverse, running every ``@on_stop``, collecting failures.

        逆序消费台账并执行 ``@on_stop``，不因单个失败中断；返回收集到的异常。
        无论成败，台账都会被清空——回收只做一次。
        """
        errors: list[Exception] = []
        while self._started:
            t = self._started.pop()
            for hook in stop_hooks(self._graph[t]):
                try:
                    await self._invoke_hook(hook)
                except Exception as exc:
                    exc.add_note(f"raised by {t.__name__}.{getattr(hook, '__name__', '<hook>')}")
                    errors.append(exc)
        return errors

    def _require(self, expected: LifecycleState) -> None:
        if self._state is not expected:
            raise LifecycleError(
                f"Canary: illegal transition from {self._state.name} (expected {expected.name})"
            )

    @staticmethod
    async def _invoke_hook(hook: _Hook) -> None:
        """Run a hook, awaiting it if the result is awaitable.

        按返回值判断（而非函数声明）更稳健：既覆盖 ``async def``，也覆盖返回协程的同步函数。
        """
        result = hook()
        if inspect.isawaitable(result):
            await result
