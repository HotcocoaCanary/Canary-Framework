"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，"嵌套""单独启动"
"组合"共用同一条代码路径。

四个动作，每个只做一件事::

    Canary(...)     装配——建图、排序、注入。同步，不跑任何钩子
    await init()    全部 @on_init
    await start()   全部 @on_start
    await stop()    逆序全部 @on_stop

``async with canary`` 与 ``canary.lifespan`` 是便利路径，进入时完成 ``init`` + ``start``、
退出时 ``stop``。钩子可同步可异步，运行时按返回值判断是否 ``await``。

运行时只做装配与生命周期，不认识任何外壳（HTTP、CLI、消息消费者……）：``canary.lifespan``
接入收异步上下文管理器的宿主，三个显式方法接入收成对启停回调的宿主。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import types
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Literal, Self, TypeVar, cast

from canary_framework.common.error import InjectionError, LifecycleError
from canary_framework.common.type import LifecycleState
from canary_framework.core.decorator.introspect import (
    deps_of,
    init_hooks,
    is_cocoa,
    start_hooks,
    stop_hooks,
)
from canary_framework.core.infra.naming import to_snake
from canary_framework.runtime.graph import build_graph, topological_sort
from canary_framework.runtime.probe import ProbeState, apply_probe, restore_probe
from canary_framework.runtime.report import assembly_summary

_log = logging.getLogger("canary.runtime")


_T = TypeVar("_T")

# 一个钩子：同步时返回 None，异步时返回可等待对象。``Callable[[], object]`` 对二者都成立。
_Hook = Callable[[], object]

# 进行中的状态：只可能被并发调用者观察到，此时再驱动生命周期属于误用。
_TRANSIENT = (LifecycleState.INITIALIZING, LifecycleState.STARTING, LifecycleState.STOPPING)


def _one_failure(group: BaseExceptionGroup) -> BaseException:
    """Unwrap a TaskGroup's ExceptionGroup back to the single real failure, when there is one.

    ``TaskGroup`` 在一个单元失败时会取消同批的其它单元，异常组里因此混有 ``CancelledError``。
    滤掉它们之后：只剩一个则原样返回（与顺序启动行为一致），剩下多个则合成一个
    ``ExceptionGroup``。
    """
    real = [exc for exc in _flatten(group) if not isinstance(exc, asyncio.CancelledError)]
    if len(real) == 1:
        return real[0]
    ordinary = [exc for exc in real if isinstance(exc, Exception)]
    if real and len(ordinary) == len(real):
        return ExceptionGroup(f"{len(real)} unit(s) failed to start", ordinary)
    return group


def _flatten(group: BaseExceptionGroup) -> list[BaseException]:
    """摊平嵌套的异常组。"""
    out: list[BaseException] = []
    for exc in group.exceptions:
        out.extend(_flatten(exc)) if isinstance(exc, BaseExceptionGroup) else out.append(exc)
    return out


class Canary:
    """A runtime that owns a graph of cocoas and drives their lifecycle.

    编排器：解析依赖图、按拓扑序驱动 ``init`` / ``start`` / ``stop``。
    异步原生——同步钩子直接调用，异步钩子自动 ``await``。
    """

    def __init__(self, *roots: type, start_concurrency: int | None = None) -> None:
        """Assemble the graph. Synchronous and complete — the runtime is usable when it returns.

        构造即装配：建图（每个类型无参构造一次）、拓扑排序、注入依赖。全部同步完成，不需要
        事件循环，也不跑任何钩子——钩子归 :meth:`init` 与 :meth:`start`。返回之后
        ``canary[SomeUnit]`` 即可取到注入好依赖的实例。

        :param roots: 一个或多个根单元，它们的依赖图会被合并为一张。
        :param start_concurrency: ``None``（默认）严格顺序启动；正整数则让互不依赖的单元
            同时启动，同时最多这么多个。
        :raises TypeError: 某个根未被 ``@cocoa`` 标记。
        :raises ValueError: ``start_concurrency`` 小于 1。
        :raises ConstructionError: 某个单元需要构造参数。
        :raises InjectionError: 某个单元的两个依赖 snake_case 撞名。
        :raises CircularDependencyError: 依赖图成环。
        """
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        if start_concurrency is not None and start_concurrency < 1:
            raise ValueError(f"start_concurrency must be at least 1, got {start_concurrency}")
        self.roots = roots
        self._concurrency = start_concurrency
        # 逐单元的钩子耗时与总耗时，供装配摘要计算并发建议。
        self._timings: dict[type, float] = {}
        self._elapsed_ms = 0.0
        self._graph: dict[type, object] = build_graph(list(roots))
        self._order: list[type] = topological_sort(self._graph)
        for t in self._order:
            self._inject(self._graph[t])
        self._state = LifecycleState.READY
        # 已进入 ``@on_start`` 的单元，按进入顺序；回收时逆序消费。
        # 记的是“进入”而非“完成”：启动到一半失败或被取消的单元同样要回收。
        self._started: list[type] = []
        # 事件循环探针改动前的旧值，停止时还原；未开启探针时为 None。
        self._loop_probe: ProbeState = None

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
        """``READY -> INITIALIZED``: run every ``@on_init``.

        按拓扑序（或按 ``start_concurrency`` 并发）跑全部 ``@on_init``。依赖已在装配期注入，
        这里做只需要依赖、不碰外部资源的准备：校验、建索引、算派生值。

        本方法的返回是一道栅栏：全部 ``@on_init`` 完成之后，才允许任何 ``@on_start`` 运行。

        失败时状态转 ``FAILED`` 并原样抛出；``@on_init`` 按契约不获取资源，台账为空，
        无需回收。
        """
        self._require(LifecycleState.READY)
        self._state = LifecycleState.INITIALIZING
        began = time.perf_counter()
        try:
            self._loop_probe = await apply_probe(self._loop_probe)
            await self._run_phase(init_hooks, ledger=False)
        except Exception:
            self._state = LifecycleState.FAILED
            raise
        self._elapsed_ms += (time.perf_counter() - began) * 1e3
        self._state = LifecycleState.INITIALIZED

    async def start(self) -> None:
        """``INITIALIZED -> STARTED``: run every ``@on_start``.

        按拓扑序（或按 ``start_concurrency`` 并发）跑全部 ``@on_start``：获取资源、起后台
        任务。单元一进入 ``@on_start`` 即记账。

        不变式是"要么全部启动，要么什么都没启动"：任一环节抛出时，台账里的单元（含失败的
        那一个）按逆序执行 ``@on_stop``，随后原样抛出最初的异常，回收过程中的异常作为 note
        附在其上。

        :raises LifecycleError: 尚未 ``init()``，或状态不是 ``INITIALIZED``。
        """
        if self._state is LifecycleState.READY:
            raise LifecycleError("Canary: call init() before start() — @on_init has not run yet")
        self._require(LifecycleState.INITIALIZED)
        self._state = LifecycleState.STARTING
        began = time.perf_counter()
        try:
            await self._run_phase(start_hooks, ledger=True)
        except Exception as exc:
            self._state = LifecycleState.FAILED
            for err in await self._unwind():
                exc.add_note(f"during rollback: {err!r}")
            raise
        self._elapsed_ms += (time.perf_counter() - began) * 1e3
        self._state = LifecycleState.STARTED
        if _log.isEnabledFor(logging.DEBUG):
            # 诊断不能反过来弄坏应用：摘要出问题只报摘要出了问题。
            try:
                _log.debug(
                    "%s",
                    assembly_summary(
                        self.roots, self._order, self._timings, self._elapsed_ms, self._concurrency
                    ),
                )
            except Exception:  # pragma: no cover - 仅防御
                _log.debug("assembly summary unavailable", exc_info=True)

    async def stop(self) -> None:
        """Reclaim everything that was started, in reverse order.

        按台账逆序执行 ``@on_stop``。它是唯一的回收路径，正常结束与失败结束共用：从
        ``STARTED`` 可调，从 ``FAILED`` 也可调，重复调用幂等，从未启动过时空转。

        单个 ``@on_stop`` 抛出不中断回收：异常被逐一收集，其余单元照常回收，最后合并为一个
        :exc:`ExceptionGroup` 抛出（哪怕只有一个）。

        :raises LifecycleError: 在某个动作进行中调用。
        :raises ExceptionGroup: 一个或多个 ``@on_stop`` 抛出。
        """
        if self._state in _TRANSIENT:
            raise LifecycleError(f"Canary: stop() is illegal while {self._state.name}")
        self._loop_probe = restore_probe(self._loop_probe)
        if not self._started:
            # 从未启动或已回收干净：空转，但不抹掉先前的失败态。
            if self._state is not LifecycleState.FAILED:
                self._state = LifecycleState.STOPPED
            return
        self._state = LifecycleState.STOPPING
        errors = await self._unwind()
        if errors:
            self._state = LifecycleState.FAILED
            raise ExceptionGroup(f"Canary: {len(errors)} error(s) while stopping", errors)
        self._state = LifecycleState.STOPPED

    # -- context manager ----------------------------------------------
    @asynccontextmanager
    async def lifespan(self, _host: object = None) -> AsyncIterator[None]:
        """The host-facing entry point: init + start on enter, stop on exit, yielding nothing.

        供宿主使用的入口，形状是 ``Callable[[Host], AsyncContextManager[None]]`` —— ASGI 的
        ``lifespan=``、MCP 的 ``MCPServer(lifespan=)``、FastStream 的 ``lifespan=`` 收的都是
        它。``_host`` 接住宿主传入的自身，带默认值以便无宿主时直接使用::

            app = FastAPI(lifespan=canary.lifespan)
            async with canary.lifespan(): ...

        它交出 ``None`` 而不是容器：ASGI 的 lifespan 协议会把交出的值当作要合并进
        ``scope["state"]`` 的映射。需要拿到容器时用 ``async with canary``。
        """
        async with self:
            yield

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
    async def _run_phase(self, hooks_of: Callable[[object], list[_Hook]], *, ledger: bool) -> None:
        """Run one whole pass of hooks over the graph, sequentially or concurrently.

        跑完一整轮钩子（:meth:`init` 的 ``@on_init`` 或 :meth:`start` 的 ``@on_start``）。

        并发模式下调度是依赖驱动的——每个单元只等自己的依赖，而不是等整个拓扑层次，因此
        耗时贴着关键路径。

        ``ledger`` 为真时在跑钩子之前记账。并发下记账顺序仍是一个合法的拓扑序（单元只在
        依赖全部完成后才进入），逆序回收因此依旧正确。
        """
        if self._concurrency is None:
            for t in self._order:
                if ledger:
                    self._started.append(t)
                await self._run_unit(t, hooks_of)
            return

        done = {t: asyncio.Event() for t in self._order}
        limit = asyncio.Semaphore(self._concurrency)

        async def run(t: type) -> None:
            for dep in deps_of(t):
                await done[dep].wait()
            # 信号量只圈住跑钩子的那段，等依赖时不占名额。
            async with limit:
                if ledger:
                    self._started.append(t)
                await self._run_unit(t, hooks_of)
            done[t].set()

        try:
            async with asyncio.TaskGroup() as group:
                for t in self._order:
                    group.create_task(run(t))
        except BaseExceptionGroup as failures:
            raise _one_failure(failures) from None

    async def _run_unit(self, t: type, hooks_of: Callable[[object], list[_Hook]]) -> None:
        """跑一个单元的钩子，并累计耗时供装配摘要使用。"""
        began = time.perf_counter()
        for hook in hooks_of(self._graph[t]):
            await self._invoke_hook(hook)
        self._timings[t] = self._timings.get(t, 0.0) + (time.perf_counter() - began) * 1e3

    def _inject(self, node: object) -> None:
        """Inject each declared dependency by its snake_case attribute name.

        按依赖类名的 snake_case 注入属性（``Database`` → ``node.database``）。两个依赖撞名
        时抛 :class:`InjectionError`，而不是后写的覆盖先写的。
        """
        cls = type(node)
        plan: dict[str, tuple[str, object]] = {}
        for dep in deps_of(cls):
            name = to_snake(dep.__name__)
            if name in plan:
                raise InjectionError(cls.__name__, name, [plan[name][0], dep.__name__])
            plan[name] = (dep.__name__, self._graph[dep])
        for name, (_declared_by, value) in plan.items():
            setattr(node, name, value)

    async def _unwind(self) -> list[Exception]:
        """Drain the ledger in reverse, running every ``@on_stop``, collecting failures.

        逆序消费台账并执行 ``@on_stop``，不因单个失败中断，返回收集到的异常。无论成败台账
        都会被清空，回收只做一次。
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

        按返回值而非函数声明判断，因此既覆盖 ``async def``，也覆盖返回协程的同步函数。
        """
        result = hook()
        if inspect.isawaitable(result):
            await result
