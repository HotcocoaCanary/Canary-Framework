"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，
让“嵌套”“单独启动”“组合”共用同一条代码路径。

四个动作，四个含义，一一对应，没有一个方法做两件事：

    Canary(...)     装配——建图、排序、注入。同步、确定性、不跑任何钩子
    await init()    各就各位——全部 @on_init
    await start()   开工——全部 @on_start
    await stop()    回收——逆序 @on_stop

``async with canary`` 与 ``canary.lifespan`` 是便利路径，定义上就是"进入时做完所有事"；
显式路径一一对应。引擎是 async 原生：钩子既可以是同步函数，也可以是协程函数，运行时按
返回值自动判断是否 ``await``。

运行时**只做装配与生命周期**，不认识任何外壳（HTTP、CLI、消息消费者……）。接进宿主有两条
路，对应 Python 世界仅有的两种宿主协议：``canary.lifespan`` 交给收异步上下文管理器的宿主
（ASGI 的 lifespan、MCP、FastStream……），三个显式方法交给收成对回调的宿主
（``on_startup`` / ``on_shutdown``）。
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

# 一个钩子：同步时返回 None，异步时返回一个可等待对象（协程）。
# ``Callable[[], object]`` 对二者都成立——协程也是 ``object`` 的子类型。
_Hook = Callable[[], object]

# 进行中的状态：只可能被并发调用者观察到，此时再驱动生命周期一定是误用。
_TRANSIENT = (LifecycleState.INITIALIZING, LifecycleState.STARTING, LifecycleState.STOPPING)


def _one_failure(group: BaseExceptionGroup) -> BaseException:
    """Unwrap a TaskGroup's ExceptionGroup back to the single real failure, when there is one.

    并发启动失败时 ``TaskGroup`` 会取消同批的其它单元，于是异常组里混着一堆
    ``CancelledError``——那些是我们自己造成的，不是原因。把它们滤掉之后：

    - 只剩一个 → 原样抛出它，和顺序启动的行为一致（调用方的 ``except RuntimeError`` 照旧管用）
    - 剩下多个 → 真的有多个单元同时失败，保留 ``ExceptionGroup``，一个都不隐瞒
    """
    real = [exc for exc in _flatten(group) if not isinstance(exc, asyncio.CancelledError)]
    if len(real) == 1:
        return real[0]
    ordinary = [exc for exc in real if isinstance(exc, Exception)]
    if real and len(ordinary) == len(real):
        return ExceptionGroup(f"{len(real)} unit(s) failed to start", ordinary)
    return group


def _flatten(group: BaseExceptionGroup) -> list[BaseException]:
    """异常组可以嵌套异常组，摊平成一层。"""
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
        """Assemble the graph. Synchronous, and complete — the runtime is usable when it returns.

        构造即装配：建图（每个类型无参构造一次）、拓扑排序、注入依赖。这三件都是同步的、
        确定性的、不跑任何使用者的运行期代码，也不需要事件循环。

        为什么放在构造函数里：这个框架对每个单元立的规矩是"构造完就必须可用"——运行时
        自己没有理由例外。装配放在这里之后，``Canary(Root)`` 一返回，``canary[Database]``
        就能取到已注入依赖的实例，装配类的错误（``ConstructionError`` / ``InjectionError``
        / ``CircularDependencyError``）也在你写下这一行的地方抛出，而不是等到某个 await。

        跑钩子的事一件不做——那是 :meth:`init` 与 :meth:`start` 各自的活。切口划在性质变化
        的地方：装配是同步的、确定性的；钩子是使用者的代码、可能异步、可能有副作用。

        ``start_concurrency`` 给启动开并发：``None``（默认）是严格顺序，与从前一致；给一个
        正整数则让**互不依赖的单元同时启动**，同时最多这么多个。默认关着有两个理由——并发
        启动会同时向下游发起 N 个连接（连接风暴），以及它会打破"兄弟按声明序启动"这个虽然
        从未承诺、但可能有人依赖的顺序。启动完成后框架会在装配摘要里告诉你开了能省多少。
        """
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        if start_concurrency is not None and start_concurrency < 1:
            raise ValueError(f"start_concurrency must be at least 1, got {start_concurrency}")
        self.roots = roots
        self._concurrency = start_concurrency
        # 每个单元跑钩子花了多久，以及 init + start 一共花了多久；摘要靠它们算"开并发能省多少"。
        self._timings: dict[type, float] = {}
        self._elapsed_ms = 0.0
        self._graph: dict[type, object] = build_graph(list(roots))
        self._order: list[type] = topological_sort(self._graph)
        for t in self._order:
            self._inject(self._graph[t])
        self._state = LifecycleState.READY
        # 已进入 ``@on_start`` 的单元，按进入顺序；回收时逆序消费。
        # 记录的是“进入”而非“完成”——启动到一半失败的单元同样要被回收。
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

        各就各位。依赖已在构造期注入完毕，这里让每个单元做它"只需要依赖、不碰外部资源"
        的准备——校验、建索引、算派生值。跑完之后整张图各就各位，**但还没有任何单元开工**。

        它单独是一个动作，因为它是一道**栅栏**：拓扑序只保证"我的依赖先于我"，管不到兄弟
        之间；只有"全部 ``@on_init`` 完成之后才允许任何 ``@on_start``"这条，能表达"整张图
        准备好了才开始对外服务"。这道栅栏就是本方法的返回——不调 :meth:`start`，谁也不会开工。

        失败时不回滚：``@on_init`` 按契约不获取资源，台账是空的，没有东西需要回收。
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

        开工。按拓扑序（或在 ``start_concurrency`` 下按依赖驱动地并发）跑全部 ``@on_start``
        ——获取资源、起后台任务。进入 ``@on_start`` 的单元立刻记账。

        不变式：**要么全部启动，要么什么都没启动。** 任一环节抛出时，台账里的单元（含失败
        的那一个）按逆序执行 ``@on_stop``，随后原样抛出最初的异常；回收过程中的异常作为
        note 附在其上，不改变异常类型。
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
            # 诊断绝不能反过来弄坏应用：摘要出问题就只报摘要出了问题。
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

        按台账逆序执行 ``@on_stop``。它是**唯一的回收路径**，同时承接正常结束与失败
        结束：从 ``STARTED`` 可调，从 ``FAILED`` 也可调，重复调用是幂等的。

        单个 ``@on_stop`` 抛出不会中断回收——异常被逐一收集，其余单元照常回收，
        最后合并成一个 :exc:`ExceptionGroup` 抛出（哪怕只有一个）。
        """
        if self._state in _TRANSIENT:
            raise LifecycleError(f"Canary: stop() is illegal while {self._state.name}")
        self._loop_probe = restore_probe(self._loop_probe)
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

    # -- context manager ----------------------------------------------
    @asynccontextmanager
    async def lifespan(self, _host: object = None) -> AsyncIterator[None]:
        """The host-facing entry point: init + start on enter, stop on exit, yield nothing.

        交给宿主的入口。它和 ``async with canary`` 只差一件事：**交出 None 而不是自己**。

        Python 世界里"一个有生命期的东西"事实上的标准就是异步上下文管理器，各领域的宿主
        收的都是同一个形状 —— ``Callable[[Host], AsyncContextManager[T]]``：ASGI 的
        ``lifespan=``（Starlette / FastAPI / Litestar）、MCP 的 ``MCPServer(lifespan=)``、
        FastStream 的 ``lifespan=`` 都是。所以 ``_host`` 收下宿主自己传进来的那个参数，
        又给了默认值，让它在没有宿主时（CLI、脚本、测试夹具）也能直接
        ``async with canary.lifespan():``。

        为什么必须交出 None：ASGI 的 lifespan 协议**把交出来的值当作要合并进
        ``scope["state"]`` 的映射**（Starlette 用它给使用者传共享状态）。``__aenter__``
        返回的是 ``self``，于是 Starlette 会去 ``dict.update(canary)``，漏出一个
        ``KeyError: 0`` —— 毫无线索。Litestar 没有这层约定，所以它直接给就能用；同一个
        协议的两种方言，这里一次性照顾到。

        ``async with canary`` 保持原样（交出容器自己），它服务的是你自己的代码::

            app = FastAPI(lifespan=canary.lifespan)      # 宿主
            async with canary as app: ...                # 你自己
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

        跑完一整轮钩子——:meth:`init` 的一轮 ``@on_init``，或 :meth:`start` 的一轮
        ``@on_start``。两轮之间的栅栏就是两个方法之间的边界。

        并发模式下不按"拓扑层次"分组，而是**每个单元等自己的依赖**：层次分组会让一个单元
        白等同层里最慢的那个，哪怕它俩毫无关系。所以调度是依赖驱动的，跑出来的时间贴着
        关键路径。

        ``ledger`` 为真时在跑钩子之前把单元记账。记的是"进入过"而非"完成"——被取消或
        中途失败的单元同样持有半个资源，同样要回收。并发下记账顺序仍然是一个合法的拓扑序
        （单元只在依赖**全部完成**之后才进入），所以逆序回收依旧正确。
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
            # 信号量只圈住真正干活的那段，等依赖的时候不占名额。
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
        """跑一个单元的钩子，顺带记下耗时——摘要靠它算"开并发能省多少"。"""
        began = time.perf_counter()
        for hook in hooks_of(self._graph[t]):
            await self._invoke_hook(hook)
        self._timings[t] = self._timings.get(t, 0.0) + (time.perf_counter() - began) * 1e3

    def _inject(self, node: object) -> None:
        """Inject each declared dependency by its snake_case attribute name.

        按依赖类名的 snake_case 注入属性（``Database`` → ``node.database``）。
        两个依赖的 snake_case 撞名时抛 :class:`InjectionError`，不再"后写的赢"。
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
