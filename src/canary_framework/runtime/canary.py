"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，
让“嵌套”“单独启动”“组合”共用同一条代码路径。引擎是 async 原生：钩子既可以是
同步函数，也可以是协程函数，运行时按返回值自动判断是否 ``await``。

``Canary`` 本身也是一个 ASGI 应用：``__call__`` 处理 lifespan 驱动生命周期，并把
http/websocket 等 scope 委托给所有 ``@web_cocoa`` 单元合并后的统一服务入口。
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from typing import Any, Literal, Self, TypeVar, cast

from canary_framework.common.error import LifecycleError
from canary_framework.common.markers import ROUTE_ENTRIES_ATTR, WEB_ATTR
from canary_framework.common.type import LifecycleState, Receive, Scope, Send
from canary_framework.core.decorator.introspect import (
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)
from canary_framework.core.infra.naming import to_snake
from canary_framework.runtime.graph import build_graph, topological_sort
from canary_framework.runtime.mounts import join_path, mount_prefixes

_T = TypeVar("_T")

# 一个钩子：同步时返回 None，异步时返回一个可等待对象（协程）。
# ``Callable[[], object]`` 对二者都成立——协程也是 ``object`` 的子类型。
_Hook = Callable[[], object]

# 路由条目：(method, path, instance, handler)
_RouteEntry = tuple[str, str, object, Callable[..., object]]


class Canary:
    """A runtime that owns a graph of cocoas and drives their lifecycle.

    编排器：解析依赖图、按拓扑序驱动 ``init`` / ``start`` / ``stop``。
    异步原生——同步钩子直接调用，异步钩子自动 ``await``。带服务单元时，``Canary``
    自身就是 ASGI 应用，可直接 ``uvicorn app:app``。
    """

    def __init__(self, *roots: type) -> None:
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        self.roots = roots
        self._state = LifecycleState.NEW
        self._graph: dict[type, object] = {}
        self._order: list[type] = []
        self._serve_app: Any | None = None

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
            self._graph = build_graph(list(self.roots))
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
        """
        self._require(LifecycleState.INITIALIZED)
        self._state = LifecycleState.STARTING
        try:
            for t in self._order:
                node = self._graph[t]
                self._inject(node)
                for hook in start_hooks(node):
                    await self._invoke_hook(hook)
            self._serve_app = self._collect_serve_app()
        except Exception:
            self._state = LifecycleState.FAILED
            raise
        self._state = LifecycleState.STARTED

    async def stop(self) -> None:
        """``STARTED -> STOPPED``: run ``@on_stop`` in reverse topological order.

        按逆拓扑序执行 ``@on_stop``。
        """
        self._require(LifecycleState.STARTED)
        self._state = LifecycleState.STOPPING
        try:
            for t in reversed(self._order):
                for hook in stop_hooks(self._graph[t]):
                    await self._invoke_hook(hook)
        except Exception:
            self._state = LifecycleState.FAILED
            raise
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
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
            elif message["type"] == "lifespan.shutdown":
                try:
                    if self.state is LifecycleState.STARTED:
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
        meta: dict[str, str] = {}  # 文档元数据取最外层单元的

        # mount_prefixes 按“根在前”的顺序返回，故最外层单元的 title/version 胜出
        for cls, prefixes in mount_prefixes(self.roots, self._graph).items():
            entries: list[_RouteEntry] | None = getattr(self._graph[cls], ROUTE_ENTRIES_ATTR, None)
            if entries is None:
                continue
            for prefix in prefixes:
                all_entries.extend(
                    (m, join_path(prefix, p), inst, fn) for m, p, inst, fn in entries
                )
            meta = meta or getattr(cls, WEB_ATTR, {})

        if not all_entries:
            return None
        from canary_framework.web.core.app import build_serve_app

        return build_serve_app(meta, all_entries)

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
        """Inject each declared dependency into *node* by snake_case attribute.

        按依赖类名的 snake_case 注入属性（``Database`` → ``node.database``）。
        """
        for dep in deps_of(type(node)):
            setattr(node, to_snake(dep.__name__), self._graph[dep])

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
