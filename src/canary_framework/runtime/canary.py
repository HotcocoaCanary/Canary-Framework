"""Canary — the runtime that owns a graph of cocoas and drives their lifecycle.

运行时：持有整张单元图并驱动生命周期。``Canary(*roots)`` 支持多根编排，
让“嵌套”“单独启动”“组合”共用同一条代码路径。

切口划在性质变化的地方：**装配是同步的，在构造函数里完成**（建图、排序、注入）；**运行是
异步的**，归 ``start`` / ``stop``。引擎是 async 原生：钩子既可以是同步函数，也可以是协程
函数，运行时按返回值自动判断是否 ``await``。

运行时**只做装配与生命周期**，不认识任何外壳（HTTP、CLI、消息消费者……）。接进宿主有两条
路，对应 Python 世界仅有的两种宿主协议：``canary.lifespan`` 交给收异步上下文管理器的宿主
（ASGI 的 lifespan、MCP、FastStream……），三个显式方法交给收成对回调的宿主
（``on_startup`` / ``on_shutdown``）。
"""

from __future__ import annotations

import inspect
import logging
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
_TRANSIENT = (LifecycleState.STARTING, LifecycleState.STOPPING)


class Canary:
    """A runtime that owns a graph of cocoas and drives their lifecycle.

    编排器：解析依赖图、按拓扑序驱动 ``init`` / ``start`` / ``stop``。
    异步原生——同步钩子直接调用，异步钩子自动 ``await``。
    """

    def __init__(self, *roots: type) -> None:
        """Assemble the graph. Synchronous, and complete — the runtime is usable when it returns.

        构造即装配：建图（每个类型无参构造一次）、拓扑排序、注入依赖。这三件都是同步的、
        确定性的、不跑任何使用者的运行期代码，也不需要事件循环。

        为什么放在构造函数里：这个框架对每个单元立的规矩是"构造完就必须可用"——运行时
        自己没有理由例外。装配放在这里之后，``Canary(Root)`` 一返回，``canary[Database]``
        就能取到已注入依赖的实例，装配类的错误（``ConstructionError`` / ``InjectionError``
        / ``CircularDependencyError``）也在你写下这一行的地方抛出，而不是等到某个 await。

        剩下的两件事——跑 ``@on_init`` 和 ``@on_start``——才是"运行"，它们要跑使用者的代码、
        可能是异步的、可能有副作用，归 :meth:`start`。切口划在性质变化的地方。
        """
        for root in roots:
            if not is_cocoa(root):
                raise TypeError(f"'{root.__name__}' is not decorated with @cocoa")
        self.roots = roots
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
    async def start(self) -> None:
        """``READY -> STARTED``: run every ``@on_init``, then every ``@on_start``.

        按拓扑序跑两轮钩子：先全部 ``@on_init``（依赖已在构造期注入完毕，此时还没有任何
        东西开始运行），再全部 ``@on_start``（获取资源、起后台任务）。

        不变式：**要么全部启动，要么什么都没启动。** 台账记录的是"进入过 ``@on_start``"
        的单元——``@on_init`` 按契约不获取资源，也就没有东西需要回收。任一环节抛出时，
        台账里的单元（含失败的那一个）按逆序执行 ``@on_stop``，随后原样抛出最初的异常；
        回收过程中的异常作为 note 附在其上，不改变异常类型。

        于是失败规则只剩一条：**``stop()`` 收台账里的一切。** ``@on_init`` 阶段失败时台账
        是空的，回滚自然是空转，不需要为它单写一条规则。
        """
        self._require(LifecycleState.READY)
        self._state = LifecycleState.STARTING
        try:
            self._loop_probe = await apply_probe(self._loop_probe)
            for t in self._order:
                for hook in init_hooks(self._graph[t]):
                    await self._invoke_hook(hook)
            for t in self._order:
                self._started.append(t)
                for hook in start_hooks(self._graph[t]):
                    await self._invoke_hook(hook)
        except Exception as exc:
            self._state = LifecycleState.FAILED
            for err in await self._unwind():
                exc.add_note(f"during rollback: {err!r}")
            raise
        self._state = LifecycleState.STARTED
        if _log.isEnabledFor(logging.DEBUG):
            # 诊断绝不能反过来弄坏应用：摘要出问题就只报摘要出了问题。
            try:
                _log.debug("%s", assembly_summary(self.roots, self._order))
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
        """The host-facing entry point: start on enter, stop on exit, yield nothing.

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
