"""Reclaiming what a phase started.

回收。依赖图不是树，一个单元可能被多个单元依赖，因此回收不能沿依赖递归：只能按台账
逆序线性进行。单个钩子失败不中断整轮回收。

回收同时撤销被回收单元在 *undoing* 阶段（以及以它为前驱的阶段）上的推进记录，因此回收之后
可以再次推进这些阶段。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.core.declare.introspect import hooks_of
from canary_framework.core.declare.phase import Phase
from canary_framework.core.runtime.invoke import invoke
from canary_framework.core.runtime.scope import Scope


async def unwind(scope: Scope, phase: Phase, *, undoing: Phase) -> list[Exception]:
    """Drain *undoing*'s ledger in reverse, running *phase*'s hooks, collecting failures.

    逆序消费 *undoing* 阶段的台账，在每个单元上执行 *phase* 的钩子。单个钩子失败不中断
    回收：异常被逐一收集并返回，其余单元照常回收。台账无论成败都会被排空，因此回收只
    进行一次；被回收的单元在 *undoing* 及其后继阶段上的推进记录一并撤销，之后可以重新推进。

    :param scope: 要回收的作用域。
    :param phase: 执行哪个阶段的钩子。
    :param undoing: 消费哪个阶段的台账。
    :return: 回收过程中收集到的异常，按发生顺序排列。
    """
    errors: list[Exception] = []
    undone = _followers(scope, undoing)
    ledger = scope.entered[undoing.name]
    while ledger:
        cls, unit = ledger.popitem()
        for name in undone:
            scope.phases.pop((cls, name), None)
        for hook in hooks_of(unit, phase):
            try:
                await invoke(hook)
            except Exception as exc:
                exc.add_note(f"raised by {type(unit).__name__}.{_name_of(hook)}")
                errors.append(exc)
    return errors


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
