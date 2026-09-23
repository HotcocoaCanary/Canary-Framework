"""Advancing one phase across a dependency graph.

推进：在依赖图上广播一个阶段，依赖先于依赖者。每个单元的每个阶段只运行一次，互不依赖的
依赖同时推进。

推进记录保存的是推进本身而非完成标志：键不存在表示未开始，未完成表示进行中（等待即可），
已完成表示结束。三种情形因此无需另设状态机；环检测也不需要额外的"进行中"集合，因为环的
唯一表现就是遇到一个尚未完成、且位于当前路径上的单元。

失败或取消的推进在结束时移除自己的记录：正在等待它的调用方收到同一个异常，之后再推进
则重新运行，因此失败可以重试。
"""

from __future__ import annotations

import asyncio

from canary_framework.core.errors import CircularDependencyError, LifecycleError
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.scope import Scope, scope_of
from canary_framework.core.meta.introspect import deps_of, hooks_of
from canary_framework.core.meta.phase import Phase

#: 调用栈每隔这么多层交还事件循环一次。单依赖本可直接 ``await`` 以省去一个任务，但连续
#: 嵌套会触及 Python 的递归上限，因此每隔若干层改为创建任务。
_TRAMPOLINE = 32


async def advance(unit: object, phase: Phase) -> None:
    """Broadcast *phase* across *unit*'s dependency graph, dependencies first.

    在 *unit* 的依赖图上推进一次 *phase*：先推进依赖，再运行自身的钩子。同一个单元的
    同一个阶段只运行一次，无论有多少单元依赖它。

    :raises LifecycleError: *phase* 声明了前驱，而前驱尚未完成。
    :raises CircularDependencyError: 依赖成环，异常携带实际走过的环路径。
    :raises ConstructionError: 某个单元需要构造参数。
    """
    await _advance(type(unit), phase, scope_of(unit))


async def _advance(cls: type, phase: Phase, scope: Scope, path: tuple[type, ...] = ()) -> None:
    """Advance *cls* through *phase* within *scope*, recording the advance itself.

    在 *scope* 内把 *cls* 推进 *phase*，并把这次推进记入作用域。*path* 是当前递归路径，
    用于环检测与错误信息。
    """
    key = (cls, phase.name)
    if (running := scope.phases.get(key)) is not None:
        # 环的唯一表现：一个尚未完成、且位于当前路径上的单元；等待它即为死锁。检测只发生
        # 在这一处，因此常规路径上没有与深度成正比的扫描。
        if not running.done() and cls in path:
            raise CircularDependencyError((*path, cls))
        await running
        return

    _require_predecessor(cls, phase, scope)

    scope.known.setdefault(phase.name, phase)
    future = scope.phases[key] = asyncio.get_running_loop().create_future()
    future.add_done_callback(_settled)
    try:
        # 按实际类型展开依赖：经 provide 登记的替身可能声明了不同的依赖。
        await _advance_deps(scope.resolve(cls), phase, scope, (*path, cls))
        unit = scope.instance(cls)
        # 进入即记账：推进到一半失败的单元同样需要回收。重新进入时移到末尾，保持拓扑序。
        ledger = scope.entered[phase.name]
        ledger.pop(cls, None)
        ledger[cls] = unit
        for hook in hooks_of(unit, phase):
            await invoke(hook)
    except asyncio.CancelledError:
        _forget(scope, key, future)
        future.cancel()
        raise
    except BaseException as exc:
        _forget(scope, key, future)
        future.set_exception(exc)
        raise
    else:
        future.set_result(None)


async def _advance_deps(cls: type, phase: Phase, scope: Scope, path: tuple[type, ...]) -> None:
    """Advance every dependency of *cls*, concurrently when there is more than one.

    互不依赖的依赖同时推进。其中一个失败时，同批的其余依赖被取消并等待结束，异常组随后
    还原为那一个真实失败。
    """
    deps = deps_of(cls)
    if not deps:
        return
    if len(deps) == 1 and len(path) % _TRAMPOLINE:
        await _advance(deps[0], phase, scope, path)
        return
    try:
        async with asyncio.TaskGroup() as group:
            for dependency in deps:
                group.create_task(_advance(dependency, phase, scope, path))
    except BaseExceptionGroup as failures:
        raise _one_failure(failures) from None


def _require_predecessor(cls: type, phase: Phase, scope: Scope) -> None:
    """Refuse to run a phase on a unit whose declared predecessor has not finished.

    前驱阶段尚未完成时抛出 :class:`LifecycleError`，以免一个阶段被静默跳过。
    """
    if phase.after is None:
        return
    done = scope.phases.get((cls, phase.after.name))
    if done is None or not done.done():
        raise LifecycleError(f"{cls.__name__}: {phase.after} has not run, call it before {phase}")


def _forget(scope: Scope, key: tuple[type, str], future: asyncio.Future[None]) -> None:
    """Drop a failed advance's record, so that advancing again runs it again.

    移除一次失败推进的记录。只移除自己那一条，以免误删之后的新推进。
    """
    if scope.phases.get(key) is future:
        del scope.phases[key]


def _settled(future: asyncio.Future[None]) -> None:
    """Retrieve a settled future's exception so the interpreter does not warn at exit.

    取走已设置的异常，避免解释器退出时报告异常未被取用。
    """
    if not future.cancelled():
        future.exception()


def _one_failure(group: BaseExceptionGroup) -> BaseException:
    """Reduce a task group's exception group back to the single real failure, when there is one.

    滤掉取消异常后：只剩一个则原样返回，与顺序推进的行为一致；剩下多个则合成一个
    ``ExceptionGroup``。
    """
    real = [exc for exc in _flatten(group) if not isinstance(exc, asyncio.CancelledError)]
    if len(real) == 1:
        return real[0]
    ordinary = [exc for exc in real if isinstance(exc, Exception)]
    if real and len(ordinary) == len(real):
        return ExceptionGroup(f"{len(real)} unit(s) failed", ordinary)
    return group


def _flatten(group: BaseExceptionGroup) -> list[BaseException]:
    """Flatten nested exception groups into one list.

    摊平嵌套的异常组。
    """
    out: list[BaseException] = []
    for exc in group.exceptions:
        out.extend(_flatten(exc)) if isinstance(exc, BaseExceptionGroup) else out.append(exc)
    return out
