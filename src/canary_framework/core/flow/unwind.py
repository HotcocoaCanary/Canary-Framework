"""Reclaiming what a phase started.

回收。依赖图不是树，一个单元可能被多个单元依赖，因此回收不沿依赖递归，而是按台账逆序
线性进行。单个钩子失败不中断整轮回收。

:func:`unwind` 回收台账中的全部或指定单元；:func:`release` 回收一个单元：仍有运行中的
单元依赖它时拒绝，否则回收它以及从此不再被需要的依赖。

回收同时撤销被回收单元在 *undoing* 阶段（以及以它为前驱的阶段）上的推进记录，因此回收之后
可以再次推进这些阶段。

回收开始之前先等待这些阶段上进行中的推进结束：否则进行中的钩子会在回收之后才获取资源，
而它的台账已被消费，再也不会被回收。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection

from canary_framework.core.errors import LifecycleError
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.scope import Scope
from canary_framework.core.meta.introspect import deps_of, hooks_of
from canary_framework.core.meta.phase import Phase


async def unwind(
    scope: Scope, phase: Phase, *, undoing: Phase, units: Collection[type] | None = None
) -> list[Exception]:
    """Drain *undoing*'s ledger in reverse, running *phase*'s hooks, collecting failures.

    逆序消费 *undoing* 阶段的台账，在每个单元上执行 *phase* 的钩子。单个钩子失败不中断
    回收：异常被逐一收集并返回，其余单元照常回收。台账无论成败都会被排空，因此回收只
    进行一次；被回收的单元在 *undoing* 及其后继阶段上的推进记录一并撤销，之后可以重新推进。

    开始回收之前，先等待 *undoing* 及其后继阶段上进行中的推进结束，无论成败。因此不要在
    这些阶段的钩子里回收它们自己：那会等待自身，永远不会返回。

    :param scope: 要回收的作用域。
    :param phase: 执行哪个阶段的钩子。
    :param undoing: 消费哪个阶段的台账。
    :param units: 只回收台账中的这些单元（以键表示）；省略时回收全部。
    :return: 回收过程中收集到的异常，按发生顺序排列。
    """
    errors: list[Exception] = []
    undone = _followers(scope, undoing)
    await _settle(scope, undone)
    ledger = scope.entered[undoing.name]
    targets = list(ledger) if units is None else [cls for cls in ledger if cls in units]
    for cls in reversed(targets):
        if (unit := ledger.pop(cls, None)) is None:
            continue
        for name in undone:
            scope.phases.pop((cls, name), None)
        for hook in hooks_of(unit, phase):
            try:
                await invoke(hook)
            except Exception as exc:
                exc.add_note(f"raised by {type(unit).__name__}.{_name_of(hook)}")
                errors.append(exc)
    return errors


async def release(scope: Scope, unit: object, phase: Phase, *, undoing: Phase) -> list[Exception]:
    """Reclaim *unit*, and every unit that nothing still running needs any more.

    回收 *unit*，以及从此不再被需要的单元：一个运行中的单元只要还能从某个被直接推进过
    *undoing* 的单元沿依赖到达，就继续运行，其余的按台账逆序回收。*unit* 从未推进或已被
    回收时，只回收不再被需要的单元。

    :raises LifecycleError: 仍有运行中的单元依赖 *unit*。此时不做任何回收。
    :return: 回收过程中收集到的异常，按发生顺序排列。
    """
    await _settle(scope, _followers(scope, undoing))
    key = scope.key_of(unit)
    running = scope.entered[undoing.name]
    dependents = [cls for cls in running if key in deps_of(scope.resolve(cls))]
    if dependents:
        names = ", ".join(cls.__name__ for cls in dependents)
        raise LifecycleError(
            f"{key.__name__} is still required by running units: {names}. Stop those first."
        )
    requested = scope.requested[undoing.name]
    requested.discard(key)
    live = _reachable(scope, requested)
    return await unwind(
        scope, phase, undoing=undoing, units=[cls for cls in running if cls not in live]
    )


def _reachable(scope: Scope, roots: Collection[type]) -> set[type]:
    """Return *roots* and everything they depend on, transitively.

    返回 *roots* 以及它们沿依赖可达的全部单元。
    """
    seen: set[type] = set()
    todo = list(roots)
    while todo:
        cls = todo.pop()
        if cls not in seen:
            seen.add(cls)
            todo.extend(deps_of(scope.resolve(cls)))
    return seen


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
