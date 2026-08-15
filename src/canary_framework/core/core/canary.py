"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，
让“嵌套”“单独启动”“组合”共用同一条代码路径。引擎是 async 原生：钩子既可以是
同步函数，也可以是协程函数，运行时按返回值自动判断是否 ``await``。
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Awaitable, Callable
from typing import Literal, Self, TypeVar, cast

from canary_framework.common.error import LifecycleError
from canary_framework.common.type import LifecycleState
from canary_framework.core.core.graph import build_graph, topological_sort
from canary_framework.core.decorator.introspect import (
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)
from canary_framework.core.infra.naming import to_snake

_T = TypeVar("_T")

# 一个钩子：同步时返回 None，异步时返回一个可等待对象（协程）。
# ``Callable[[], object]`` 对二者都成立——协程也是 ``object`` 的子类型。
_Hook = Callable[[], object]


class Canary:
    """A runtime that owns a graph of cocoas and drives their lifecycle.

    编排器：解析依赖图、按拓扑序驱动 ``init`` / ``start`` / ``stop``。
    异步原生——同步钩子直接调用，异步钩子自动 ``await``。
    """

    def __init__(self, *roots: type) -> None:
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        self.roots = roots
        self._state = LifecycleState.NEW
        self._graph: dict[type, object] = {}
        self._order: list[type] = []

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
        """``INITIALIZED -> STARTED``: inject deps (lazy) and run ``@on_start``.

        注入依赖（懒注入），按序执行 ``@on_start``。
        """
        self._require(LifecycleState.INITIALIZED)
        self._state = LifecycleState.STARTING
        try:
            for t in self._order:
                node = self._graph[t]
                self._inject(node)
                for hook in start_hooks(node):
                    await self._invoke_hook(hook)
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

    async def _invoke_hook(self, hook: _Hook) -> None:
        """Run a hook, awaiting it if the result is awaitable.

        按返回值判断（而非函数声明）更稳健：既覆盖 ``async def``，也覆盖返回协程的同步函数。
        """
        result = hook()
        if inspect.isawaitable(result):
            await cast(Awaitable[object], result)
