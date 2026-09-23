"""Leaving a phase.

离开：进入的镜像。进入先依赖、后本单元；离开先本单元，再沿依赖图递归尝试它的依赖。

离开一个单元：

1. 它仍被使用——某个依赖者处于进入中、已进入、失败未离开或离开中——则跳过它自己，不报错；
2. 否则运行它的离开钩子（如果它持有该阶段获取的东西），它随即回到空闲，以该阶段为前驱的
   阶段也一并回到空闲；
3. 无论它自己是否被跳过，都对它的每个依赖递归尝试离开，同时进行，各在一个任务里——递归
   因此不受调用栈深度约束。

被跳过或本就空闲的单元一次调用只穿过一次；真正离开的单元每次都级联到依赖，因为某个依赖
可能刚刚失去最后一个使用者。一次调用的工作量因此与图的规模成正比。

同一个单元同时被多条路径离开时只离开一次，后到者等待；它正在进入时，先等进入结束。进入
失败的单元立即离开（见 :mod:`~canary_framework.core.flow.enter`），此时不检查是否被使用：
等待它的依赖者从未用到它。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from canary_framework.core.errors import LifecycleError
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.scope import IN_USE, Scope, State, scope_of
from canary_framework.core.meta.introspect import hooks_of
from canary_framework.core.meta.phase import Phase


async def leave(unit: object, phase: Phase) -> None:
    """Leave *phase* on *unit*, then try its dependencies the same way.

    离开 *unit* 的 *phase*：它仍被使用时跳过；否则运行 ``phase.leave`` 的钩子。然后沿依赖图
    递归尝试它的依赖。在根单元上即整张图。

    :raises LifecycleError: *phase* 没有声明 ``leave``。
    :raises ExceptionGroup: 一个或多个离开钩子抛出异常，即使只有一个；其余单元照常离开。
    """
    if phase.leave is None:
        raise LifecycleError(f"{phase} declares no leave phase, so it cannot be left")
    scope = scope_of(unit)
    key = scope.key_of(unit)
    errors: list[Exception] = []
    if key in scope.graph:
        await _leave(scope, key, _Pass(phase, _left_with(scope, phase), errors))
    if errors:
        raise ExceptionGroup(f"{len(errors)} error(s) while leaving {phase}", errors)


async def rollback(scope: Scope, cls: type, phase: Phase) -> list[Exception]:
    """Undo a failed entering of *phase* on *cls*, whoever waits on it.

    进入失败或被取消的单元立即回到空闲。阶段声明了 ``leave`` 时先离开——不检查是否被使用，
    等待它的依赖者从未用到它；没有声明时它没有获取任何东西，直接重置。由进入调用。

    :return: 离开钩子抛出的异常。
    """
    errors: list[Exception] = []
    if phase.leave is None:
        scope.track(cls, phase).reset()
    else:
        await _leave(scope, cls, _Pass(phase, _left_with(scope, phase), errors), failed=True)
    return errors


@dataclass(slots=True)
class _Pass:
    """What one call to leave shares across every unit it reaches.

    一次离开调用在所经过的全部单元之间共享的东西。
    """

    phase: Phase
    #: *phase* 以及以它为前驱的阶段：离开时一并回到空闲。每次调用只算一次。
    left: tuple[Phase, ...]
    errors: list[Exception]
    #: 被跳过或本就空闲、已经穿过的单元。
    seen: set[type] = field(default_factory=set)


async def _leave(scope: Scope, cls: type, run: _Pass, *, failed: bool = False) -> None:
    """Leave one unit, then try its dependencies. See the module docstring for the rules.

    离开一个单元，再尝试它的依赖。
    """
    phase = run.phase
    track = scope.track(cls, phase)
    while True:
        if track.leaving is not None:
            await asyncio.wait([track.leaving])
            return
        if track.state is not State.ENTERING:
            break
        assert track.outcome is not None
        await asyncio.wait([track.outcome])  # 它正在进入：等进入结束再决定
    if track.state is State.IDLE or (not failed and _in_use(scope, cls, phase)):
        # 本就空闲，或仍被使用：它自己不变，只穿过一次去尝试它的依赖
        if cls not in run.seen:
            run.seen.add(cls)
            await _each(scope, scope.graph.get(cls, ()), run)
        return
    assert phase.leave is not None
    track.leaving = asyncio.get_running_loop().create_future()
    try:
        track.state = State.LEAVING
        try:
            unit, track.unit = track.unit, None
            if unit is not None:
                for hook in hooks_of(unit, phase.leave):
                    try:
                        await invoke(hook)
                    except Exception as exc:
                        exc.add_note(f"raised by {type(unit).__name__}.{_name_of(hook)}")
                        run.errors.append(exc)
        finally:
            for left in run.left:
                scope.track(cls, left).reset()
        # 从这里起它不再使用自己的依赖
        await _each(scope, scope.graph.get(cls, ()), run)
    finally:
        done, track.leaving = track.leaving, None
        done.set_result(None)


async def _each(scope: Scope, targets: Iterable[type], run: _Pass) -> None:
    """Try to leave every target concurrently, each in a task of its own.

    同时尝试离开每个目标。被取消时连带取消这些任务：尚未轮到的单元仍持有它获取的东西，
    再次离开时继续。
    """
    tasks = [asyncio.create_task(_leave(scope, cls, run)) for cls in targets]
    await wait_all(tasks)
    for task in tasks:
        if not task.cancelled() and (exc := task.exception()) is not None:
            raise exc


async def wait_all(tasks: list[asyncio.Task[None]]) -> None:
    """Wait for every task; if cancelled meanwhile, cancel them all, wait, and re-raise.

    等待全部任务结束。等待期间被取消时，连带取消这些任务并等它们结束，再抛出取消。
    """
    if not tasks:
        return
    try:
        await asyncio.wait(tasks)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.wait(tasks)
        raise


def _in_use(scope: Scope, cls: type, phase: Phase) -> bool:
    """Whether a dependent of *cls* is entering, entered, failed without leaving, or leaving.

    是否有依赖者仍在使用它。
    """
    for dependent in scope.dependents.get(cls, ()):
        track = scope.tracks.get((dependent, phase.name))
        if track is not None and track.state in IN_USE:
            return True
    return False


def _left_with(scope: Scope, phase: Phase) -> tuple[Phase, ...]:
    """Return *phase* and the phases entered in *scope* whose predecessors include it.

    返回 *phase* 以及本作用域进入过的、前驱链上含有 *phase* 的阶段。它们以 *phase* 为前提，
    *phase* 被离开时它们也随之回到空闲。
    """
    found = [phase]
    for other in scope.known.values():
        after = other.after
        while after is not None:
            if after.name == phase.name:
                found.append(other)
                break
            after = after.after
    return tuple(found)


def _name_of(hook: Callable[[], object]) -> str:
    """Return the hook's name for use in an error note.

    返回钩子名，用于错误提示。
    """
    return getattr(hook, "__name__", "<hook>")
