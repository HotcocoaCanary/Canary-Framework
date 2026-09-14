"""Reclaiming what a phase started.

回收。依赖图不是树，一个单元可能被多个单元依赖，因此回收不能沿依赖递归：只能按台账
逆序线性进行。单个钩子失败不中断整轮回收。
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
    进行一次。

    :param scope: 要回收的作用域。
    :param phase: 执行哪个阶段的钩子。
    :param undoing: 消费哪个阶段的台账。
    :return: 回收过程中收集到的异常，按发生顺序排列。
    """
    errors: list[Exception] = []
    ledger = scope.entered[undoing.name]
    while ledger:
        unit = ledger.pop()
        for hook in hooks_of(unit, phase):
            try:
                await invoke(hook)
            except Exception as exc:
                exc.add_note(f"raised by {type(unit).__name__}.{_name_of(hook)}")
                errors.append(exc)
    return errors


def _name_of(hook: Callable[[], object]) -> str:
    """Return the hook's name for use in an error note.

    返回钩子名，用于错误提示。
    """
    return getattr(hook, "__name__", "<hook>")
