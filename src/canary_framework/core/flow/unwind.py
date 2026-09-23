"""Releasing what a phase acquired.

释放：与推进互为镜像。推进先依赖后本单元；释放先本单元，再沿依赖图递归尝试释放依赖。

释放一个单元（:func:`release`）：

1. 它正被使用——有依赖者正在推进、已经推进、或正在执行撤销钩子——则跳过它自己，不报错；
2. 否则执行它的撤销钩子（如果它进入过该阶段），并撤销它在该阶段及后继阶段上的推进记录，
   此后它不再使用自己的依赖；
3. 无论它自己是否被跳过，都对它的每个依赖递归尝试释放，互不依赖的同时进行。

被跳过或本就未运行的单元，一次释放中只被穿过一次；真正被停止的单元每次都级联到依赖——
一个依赖可能要等最后一个使用者停止之后才空闲。两者合起来，一次释放的工作量与图的规模
成正比。

同一个单元同时被多条路径释放时只执行一次，后到者只等待。一个单元在推进中失败或被取消时
立即释放自己（见 :mod:`~canary_framework.core.flow.advance`），此时不检查是否被使用：
还在等待它的依赖者从未用到它。

:func:`unwind` 释放某个阶段台账中的全部单元。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection

from canary_framework.core.errors import LifecycleError
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.scope import Scope
from canary_framework.core.meta.introspect import hooks_of
from canary_framework.core.meta.phase import Phase


async def release(scope: Scope, unit: object, phase: Phase) -> list[Exception]:
    """Release *unit* from *phase*, then try to release its dependencies.

    释放 *unit*：它正被使用时跳过；否则执行 ``phase.undo`` 的钩子，再递归尝试释放它的
    依赖。*unit* 自己正在推进 *phase* 时，先等这次推进结束。

    :raises LifecycleError: *phase* 没有声明 ``undo``。
    :return: 撤销钩子抛出的异常。
    """
    if phase.undo is None:
        raise LifecycleError(f"{phase} declares no undo phase, so it cannot be released")
    key = scope.key_of(unit)
    errors: list[Exception] = []
    if key in scope.graph:
        await _release(scope, key, phase, phase.undo, errors, set())
    return errors


async def unwind(scope: Scope, phase: Phase, *, undoing: Phase) -> list[Exception]:
    """Release every unit in *undoing*'s ledger, running *phase*'s hooks, collecting failures.

    释放 *undoing* 阶段台账中的全部单元，在每个单元上执行 *phase* 的钩子。开始之前先等待
    *undoing* 及其后继阶段上进行中的推进结束。正被台账中其他单元使用的单元，在使用者释放
    之后经由递归释放。

    :return: 回收过程中收集到的异常。
    """
    await _settle(scope, _followers(scope, undoing))
    errors: list[Exception] = []
    targets = [cls for cls in scope.entered[undoing.name] if cls in scope.graph]
    await _each(scope, targets, undoing, phase, errors, set())
    return errors


async def rollback(scope: Scope, cls: type, phase: Phase) -> list[Exception]:
    """Release *cls* right after it failed to advance through *phase*, whoever waits on it.

    推进失败或被取消的单元立即释放自己：不检查是否被使用。由推进调用。
    """
    errors: list[Exception] = []
    if phase.undo is not None:
        await _release(scope, cls, phase, phase.undo, errors, set(), failed=True)
    return errors


async def _release(
    scope: Scope,
    cls: type,
    holding: Phase,
    hooks: Phase,
    errors: list[Exception],
    seen: set[type],
    *,
    failed: bool = False,
) -> None:
    """Release one unit, then try its dependencies. See the module docstring for the rules.

    释放一个单元，再尝试释放它的依赖。
    """
    key = (cls, holding.name)
    while True:
        if (busy := scope.releasing.get(key)) is not None:
            await asyncio.wait([busy])
            return
        record = scope.phases.get(key)
        if record is None or record.done():
            break
        await asyncio.wait([record])  # 它自己正在推进：等推进结束再决定
    ledger = scope.entered[holding.name]
    skipped = not failed and _in_use(scope, cls, holding)
    if skipped or (record is None and cls not in ledger):
        # 被使用，或本就未运行：它自己不变，只穿过一次去尝试它的依赖
        if cls not in seen:
            seen.add(cls)
            await _each(scope, list(scope.graph.get(cls, ())), holding, hooks, errors, seen)
        return
    done = scope.releasing[key] = asyncio.get_running_loop().create_future()
    try:
        scope.stopping.add(key)
        try:
            unit = ledger.pop(cls, None)
            if unit is not None:
                for hook in hooks_of(unit, hooks):
                    try:
                        await invoke(hook)
                    except Exception as exc:
                        exc.add_note(f"raised by {type(unit).__name__}.{_name_of(hook)}")
                        errors.append(exc)
        finally:
            for name in _followers(scope, holding):
                scope.phases.pop((cls, name), None)
            scope.stopping.discard(key)
        # 从这里起它不再使用自己的依赖
        await _each(scope, list(scope.graph.get(cls, ())), holding, hooks, errors, seen)
    finally:
        del scope.releasing[key]
        done.set_result(None)


async def _each(
    scope: Scope,
    targets: list[type],
    holding: Phase,
    hooks: Phase,
    errors: list[Exception],
    seen: set[type],
) -> None:
    """Try to release every target concurrently, each in a task of its own.

    同时尝试释放每个目标，各在一个任务里——递归因此不受调用栈深度约束。被取消时连带取消
    这些任务：尚未开始的单元留在台账里，再次释放时继续。
    """
    tasks = [
        asyncio.create_task(_release(scope, cls, holding, hooks, errors, seen)) for cls in targets
    ]
    if not tasks:
        return
    try:
        await asyncio.wait(tasks)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        raise
    for task in tasks:
        if not task.cancelled() and (exc := task.exception()) is not None:
            raise exc


def _in_use(scope: Scope, cls: type, holding: Phase) -> bool:
    """Whether a dependent of *cls* is advancing, has advanced, or is still undoing *holding*.

    是否有依赖者正在推进、已经推进（包括推进失败但尚未释放）、或正在执行撤销钩子。
    """
    ledger = scope.entered[holding.name]
    for dependent in scope.dependents.get(cls, ()):
        key = (dependent, holding.name)
        record = scope.phases.get(key)
        if record is not None and (not record.done() or _succeeded(record)):
            return True
        if dependent in ledger or key in scope.stopping:
            return True
    return False


def _succeeded(future: asyncio.Future[None]) -> bool:
    return not future.cancelled() and future.exception() is None


async def _settle(scope: Scope, names: Collection[str]) -> None:
    """Wait until no advance of the phases in *names* is in flight in *scope*.

    等待 *names* 中各阶段在 *scope* 内进行中的推进全部结束。进行中的推进可能再推进新的
    依赖，因此反复检查直到没有进行中的推进。推进的异常由它自己的调用方接收，这里不取。
    """
    while pending := [
        future for (_, name), future in scope.phases.items() if name in names and not future.done()
    ]:
        await asyncio.wait(pending)


def _followers(scope: Scope, undoing: Phase) -> tuple[str, ...]:
    """Return *undoing* and every phase advanced in *scope* that requires it, by name.

    返回 *undoing* 以及本作用域推进过的、前驱链上含有 *undoing* 的全部阶段名。这些阶段
    以 *undoing* 为前提，前提被撤销时它们的记录也随之失效。
    """
    names = [undoing.name]
    for phase in scope.known.values():
        after = phase.after
        while after is not None:
            if after.name == undoing.name:
                names.append(phase.name)
                break
            after = after.after
    return tuple(names)


def _name_of(hook: Callable[[], object]) -> str:
    """Return the hook's name for use in an error note.

    返回钩子名，用于错误提示。
    """
    return getattr(hook, "__name__", "<hook>")
