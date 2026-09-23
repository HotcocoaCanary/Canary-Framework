"""Advancing one phase across a dependency graph.

推进：在依赖图上推进一个阶段，依赖先于依赖者。每个单元的每个阶段只运行一次，互不依赖的
单元同时推进。

推进之前先把单元连同它的依赖加入依赖图（见 :mod:`~canary_framework.core.flow.graph`），
环因此在任何钩子运行之前就被发现；前驱阶段也在此时一并检查。随后每个单元一个任务：等它的
依赖完成，再运行它的钩子。没有递归，依赖链的深度不受 Python 递归上限约束。

一个单元失败时不取消其他单元：每个单元各自完成。依赖未能全部完成的单元不运行钩子，以
同一个异常失败。阶段声明了 ``undo`` 时，失败或被取消的单元立即释放自己，再尝试释放它的
依赖（见 :mod:`~canary_framework.core.flow.unwind`）；因此一次失败的推进返回时，它为此
获取的一切都已释放，只有仍被其他单元使用的除外。

推进记录保存的是推进本身而非完成标志：键不存在表示未开始，未完成表示进行中（等待即可），
已完成表示结束。另一次推进正在进行的单元不会被再运行一遍，而是被等待。

失败或取消的推进在本次 :func:`advance` 期间保留记录，:func:`advance` 返回时清除，之后再
推进则重新运行，因此失败可以重试。

等待另一个单元的推进经过 :func:`asyncio.shield`：一个等待者被取消（例如兄弟单元失败后
其余任务被取消），不会连带取消这次共享的推进。
"""

from __future__ import annotations

import asyncio

from canary_framework.core.errors import LifecycleError
from canary_framework.core.flow.graph import closure, include
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.scope import Scope, scope_of
from canary_framework.core.flow.unwind import rollback
from canary_framework.core.meta.introspect import hooks_of
from canary_framework.core.meta.phase import Phase


async def advance(unit: object, phase: Phase) -> None:
    """Advance *phase* across *unit*'s dependency graph, dependencies first.

    在 *unit* 的依赖图上推进一次 *phase*：依赖先于依赖者，互不依赖的单元同时推进。同一个
    单元的同一个阶段只运行一次，无论有多少单元依赖它。任何钩子运行之前，先检查依赖是否
    成环、前驱阶段是否已完成。

    :raises LifecycleError: *phase* 声明了前驱，而某个待推进的单元的前驱尚未完成。
    :raises CircularDependencyError: 依赖成环，异常携带走到环上的路径。
    :raises ConstructionError: 某个单元需要构造参数。
    """
    scope = scope_of(unit)
    root = scope.key_of(unit)
    include(scope, root)
    nodes = closure(scope, root)
    for cls in nodes:
        if (cls, phase.name) not in scope.phases:
            _require_predecessor(cls, phase, scope)
    scope.known.setdefault(phase.name, phase)
    try:
        await _run(scope, phase, nodes)
    finally:
        _forget_failures(scope, phase)


async def _run(scope: Scope, phase: Phase, nodes: list[type]) -> None:
    """Run *phase* on every node not already advanced, each once its dependencies are done.

    认领尚无记录的节点并各建一个任务；已完成或正由另一次推进进行的节点只被等待。每个任务
    各自完成——失败不取消其他任务——之后把真实的失败汇总抛出。调用方取消时，取消全部任务
    并等待它们回滚完毕：取消之前已发生的真实失败优先抛出；否则照常抛出取消，回滚中撤销
    钩子的失败交给事件循环的异常处理器——取消本身无法携带它们。
    """
    loop = asyncio.get_running_loop()
    records: dict[type, asyncio.Future[None]] = {}
    claimed: list[type] = []
    for cls in nodes:
        key = (cls, phase.name)
        if (record := scope.phases.get(key)) is None:
            record = scope.phases[key] = loop.create_future()
            record.add_done_callback(_settled)
            claimed.append(cls)
        records[cls] = record
    undo_errors: list[Exception] = []
    tasks = [
        asyncio.create_task(
            _step(
                scope, phase, cls, [records[d] for d in scope.graph[cls]], records[cls], undo_errors
            )
        )
        for cls in claimed
    ]
    if tasks:
        try:
            await asyncio.wait(tasks)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks)
            _raise_failures(tasks)  # 取消之前已发生的真实失败优先，不被取消吞掉
            loop = asyncio.get_running_loop()
            for error in undo_errors:
                loop.call_exception_handler(
                    {"message": "error while rolling back a cancelled advance", "exception": error}
                )
            raise
        _raise_failures(tasks)
    # 根节点可能正由另一次推进进行
    root = records[nodes[-1]]
    await asyncio.wait([root])
    if root.cancelled():
        raise asyncio.CancelledError()
    if (failure := root.exception()) is not None:
        raise failure


async def _step(
    scope: Scope,
    phase: Phase,
    cls: type,
    waits: list[asyncio.Future[None]],
    record: asyncio.Future[None],
    undo_errors: list[Exception],
) -> None:
    """Advance one node once its dependencies are done, settling its record.

    等依赖全部结束，再推进这一个节点，并把结果写入它的推进记录。有依赖未能完成时不运行
    钩子，以该依赖的异常失败。失败或被取消时立即回滚（回滚本身不会被取消打断），回滚中
    撤销钩子的异常作为 note 附在原异常上。
    """
    try:
        if waits:
            await asyncio.wait(waits)  # 不取依赖的异常，也不会连带取消依赖
        for dependency in waits:
            if not _succeeded(dependency):
                raise _cause_of(dependency, cls)
        unit = scope.instance(cls)
        # 进入即记账：推进到一半失败的单元同样需要回收。重新进入时移到末尾，保持拓扑序。
        ledger = scope.entered[phase.name]
        ledger.pop(cls, None)
        ledger[cls] = unit
        for hook in hooks_of(unit, phase):
            await invoke(hook)
    except BaseException as exc:
        if isinstance(exc, asyncio.CancelledError):
            record.cancel()
        else:
            record.set_exception(exc)
        undo = asyncio.ensure_future(rollback(scope, cls, phase))
        while not undo.done():
            try:
                await asyncio.shield(undo)
            except asyncio.CancelledError:
                continue  # 回滚必须完成；取消在回滚之后照常抛出
        for error in undo.result():
            exc.add_note(f"during rollback: {error!r}")
            undo_errors.append(error)
        raise
    else:
        record.set_result(None)


def _require_predecessor(cls: type, phase: Phase, scope: Scope) -> None:
    """Refuse to run a phase on a unit whose declared predecessor has not finished.

    前驱阶段尚未完成时抛出 :class:`LifecycleError`，以免一个阶段被静默跳过。
    """
    if phase.after is None:
        return
    done = scope.phases.get((cls, phase.after.name))
    if done is None or not _succeeded(done):
        raise LifecycleError(f"{cls.__name__}: {phase.after} has not run, call it before {phase}")


def _raise_failures(tasks: list[asyncio.Task[None]]) -> None:
    """Raise the real failures among finished *tasks*, if any, ignoring cancellations.

    抛出已结束任务中的真实失败（按对象去重），忽略取消。
    """
    failures = [task.exception() for task in tasks if not task.cancelled()]
    real = [
        exc for exc in failures if exc is not None and not isinstance(exc, asyncio.CancelledError)
    ]
    if real:
        raise _one_failure(BaseExceptionGroup("advance failed", real))


def _cause_of(dependency: asyncio.Future[None], cls: type) -> BaseException:
    """The exception a node fails with when *dependency* did not complete.

    依赖失败时沿用它的异常对象（汇总时按对象去重，同一个失败只报告一次）；依赖被取消时
    以 :class:`LifecycleError` 说明原因。
    """
    if dependency.cancelled():
        return LifecycleError(f"{cls.__name__}: a dependency was cancelled before it started")
    exc = dependency.exception()
    assert exc is not None
    return exc


def _succeeded(future: asyncio.Future[None]) -> bool:
    """Whether *future* records an advance that finished without error.

    推进是否已成功结束。
    """
    return future.done() and not future.cancelled() and future.exception() is None


def _forget_failures(scope: Scope, phase: Phase) -> None:
    """Drop the records of *phase*'s failed or cancelled advances, so that they can be retried.

    清除 *phase* 上已结束但失败或被取消的推进记录。进行中与成功的记录保留。
    """
    for key in [
        key
        for key, future in scope.phases.items()
        if key[1] == phase.name and future.done() and not _succeeded(future)
    ]:
        del scope.phases[key]


def _settled(future: asyncio.Future[None]) -> None:
    """Retrieve a settled future's exception so the interpreter does not warn at exit.

    取走已设置的异常，避免解释器退出时报告异常未被取用。
    """
    if not future.cancelled():
        future.exception()


def _one_failure(group: BaseExceptionGroup) -> BaseException:
    """Reduce a task group's exception group back to the single real failure, when there is one.

    滤掉取消异常并按对象去重后：只剩一个则原样返回，与顺序推进的行为一致；剩下多个则
    合成一个 ``ExceptionGroup``。去重是因为等待同一次失败推进的多个节点，拿到的是同一个
    异常对象。
    """
    flat = _flatten(group)
    real = list(
        {id(exc): exc for exc in flat if not isinstance(exc, asyncio.CancelledError)}.values()
    )
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
