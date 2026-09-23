"""Entering a phase across a dependency graph.

进入：在依赖图上进入一个阶段，依赖先于依赖者。每个单元的每个阶段只运行一次，互不依赖的
单元同时进入。

进入之前先把单元连同它的依赖加入依赖图（见 :mod:`~canary_framework.core.flow.graph`），
环因此在任何钩子运行之前就被发现；前驱阶段也在此时一并检查。随后认领其中空闲的单元，每个
一个任务：等它的依赖进入完毕，再运行它的钩子。没有递归，依赖链的深度不受 Python 递归上限
约束。已进入、或正由另一次调用进入的单元只被等待，不会再运行一遍。

一个单元失败时不取消其他单元：每个单元各自完成。依赖未能全部进入的单元不运行钩子，以同一
个异常失败。阶段声明了 ``leave`` 时，失败或被取消的单元立即离开（见
:mod:`~canary_framework.core.flow.leave`），因此一次失败的进入返回时，它为此获取的一切都已
释放，仍被其他单元使用的除外。没有声明 ``leave`` 的阶段，失败的单元在本次调用返回时回到
空闲，因此可以重试。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from canary_framework.core.errors import LifecycleError
from canary_framework.core.flow.graph import closure, include
from canary_framework.core.flow.invoke import invoke
from canary_framework.core.flow.leave import rollback
from canary_framework.core.flow.scope import Scope, State, scope_of
from canary_framework.core.meta.introspect import hooks_of
from canary_framework.core.meta.phase import Phase


async def enter(unit: object, phase: Phase) -> None:
    """Enter *phase* across *unit*'s dependency graph, dependencies first.

    在 *unit* 的依赖图上进入一次 *phase*：依赖先于依赖者，互不依赖的单元同时进入。同一个
    单元的同一个阶段只运行一次，无论有多少单元依赖它。任何钩子运行之前，先检查依赖是否
    成环、前驱阶段是否已进入。

    :raises LifecycleError: *phase* 声明了前驱，而某个待进入的单元尚未进入前驱。
    :raises CircularDependencyError: 依赖成环，异常携带走到环上的路径。
    :raises ConstructionError: 某个单元需要构造参数。
    """
    scope = scope_of(unit)
    root = scope.key_of(unit)
    include(scope, root)
    nodes = closure(scope, root)
    for cls in nodes:
        if scope.track(cls, phase).state is State.IDLE:
            _require_predecessor(scope, cls, phase)
    scope.known.setdefault(phase.name, phase)
    await _run(scope, phase, nodes)


async def _run(scope: Scope, phase: Phase, nodes: list[type]) -> None:
    """Enter *phase* on every idle node, each once its dependencies have entered.

    认领空闲的节点，各建一个任务；其余节点只被等待。每个任务各自完成——失败不取消其他
    任务——之后把真实的失败汇总抛出。调用方取消时，取消全部任务并等待它们离开完毕：取消
    之前已发生的真实失败优先抛出；否则照常抛出取消，离开钩子的失败交给事件循环的异常
    处理器——取消本身无法携带它们。
    """
    for cls in nodes:  # 正在离开的节点先离开完，再决定是否认领
        while (leaving := scope.track(cls, phase).leaving) is not None:
            await asyncio.wait([leaving])
    loop = asyncio.get_running_loop()
    outcomes: dict[type, asyncio.Future[None]] = {}
    claimed: list[type] = []
    for cls in nodes:
        track = scope.track(cls, phase)
        if track.state is State.IDLE:
            track.state = State.ENTERING
            track.outcome = loop.create_future()
            track.outcome.add_done_callback(_settled)
            claimed.append(cls)
        assert track.outcome is not None
        outcomes[cls] = track.outcome
    leave_errors: list[Exception] = []
    tasks = [
        asyncio.create_task(
            _step(scope, phase, cls, [outcomes[d] for d in scope.graph[cls]], leave_errors)
        )
        for cls in claimed
    ]
    try:
        if tasks:
            try:
                await asyncio.wait(tasks)
            except asyncio.CancelledError:
                for task in tasks:
                    task.cancel()
                await asyncio.wait(tasks)
                _raise_failures(tasks)  # 取消之前已发生的真实失败优先，不被取消吞掉
                for error in leave_errors:
                    loop.call_exception_handler(
                        {"message": "error while leaving a cancelled enter", "exception": error}
                    )
                raise
            _raise_failures(tasks)
    finally:
        for cls in claimed:  # 没有 leave 的阶段：失败的节点回到空闲，以便重试
            if (track := scope.track(cls, phase)).state is State.FAILED:
                track.reset()
    # 根节点可能正由另一次调用进入
    root = outcomes[nodes[-1]]
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
    leave_errors: list[Exception],
) -> None:
    """Enter one node once its dependencies have entered, and settle its outcome.

    等依赖全部结束，再进入这一个节点，并写入它的结果。有依赖未能进入时不运行钩子，以该依赖
    的异常失败。失败或被取消时立即离开，离开钩子的异常作为 note 附在原异常上。
    """
    track = scope.track(cls, phase)
    outcome = track.outcome
    assert outcome is not None
    try:
        if waits:
            await asyncio.wait(waits)  # 不取依赖的异常，也不会连带取消依赖
        for dependency in waits:
            if not _succeeded(dependency):
                raise _cause_of(dependency, cls)
        track.unit = scope.instance(cls)
        for hook in hooks_of(track.unit, phase):
            await invoke(hook)
    except BaseException as exc:
        track.state = State.FAILED
        if isinstance(exc, asyncio.CancelledError):
            outcome.cancel()
        else:
            outcome.set_exception(exc)
        for error in await _uninterrupted(rollback(scope, cls, phase)):
            exc.add_note(f"during rollback: {error!r}")
            leave_errors.append(error)
        raise
    else:
        track.state = State.ENTERED
        outcome.set_result(None)


async def _uninterrupted[T](work: Awaitable[T]) -> T:
    """Await *work* to completion, riding out any cancellation of the caller.

    等 *work* 完成，期间对调用方的取消不予理会——调用方随后照常抛出它自己的异常。用于回滚：
    已经获取的东西必须释放。
    """
    task = asyncio.ensure_future(work)
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


def _require_predecessor(scope: Scope, cls: type, phase: Phase) -> None:
    """Refuse to enter a phase on a unit that has not entered its declared predecessor.

    单元尚未进入前驱阶段时抛出 :class:`LifecycleError`，以免一个阶段被静默跳过。
    """
    if phase.after is not None and scope.track(cls, phase.after).state is not State.ENTERED:
        raise LifecycleError(f"{cls.__name__}: {phase.after} has not run, call it before {phase}")


def _succeeded(future: asyncio.Future[None]) -> bool:
    """Whether a settled outcome is a success.

    结果是否成功。
    """
    return not future.cancelled() and future.exception() is None


def _cause_of(dependency: asyncio.Future[None], cls: type) -> BaseException:
    """The exception a node fails with when *dependency* did not enter.

    依赖失败时沿用它的异常对象（汇总时按对象去重，同一个失败只报告一次）；依赖被取消时
    以 :class:`LifecycleError` 说明原因。
    """
    if dependency.cancelled():
        return LifecycleError(f"{cls.__name__}: a dependency was cancelled before it entered")
    exc = dependency.exception()
    assert exc is not None
    return exc


def _raise_failures(tasks: list[asyncio.Task[None]]) -> None:
    """Raise the real failures among finished *tasks*, if any, ignoring cancellations.

    抛出已结束任务中的真实失败，忽略取消。
    """
    failures = [task.exception() for task in tasks if not task.cancelled()]
    real = [
        exc for exc in failures if exc is not None and not isinstance(exc, asyncio.CancelledError)
    ]
    if real:
        raise _one_failure(real)


def _one_failure(failures: list[BaseException]) -> BaseException:
    """Reduce *failures* to one exception: the lone failure, or a group of distinct ones.

    按对象去重之后：只剩一个则原样返回；剩下多个则合成一个 ``ExceptionGroup``。去重是因为
    等待同一个失败节点的多个依赖者，拿到的是同一个异常对象。
    """
    distinct = list({id(exc): exc for exc in failures}.values())
    if len(distinct) == 1:
        return distinct[0]
    ordinary = [exc for exc in distinct if isinstance(exc, Exception)]
    if len(ordinary) == len(distinct):
        return ExceptionGroup(f"{len(distinct)} unit(s) failed", ordinary)
    return BaseExceptionGroup(f"{len(distinct)} unit(s) failed", distinct)


def _settled(future: asyncio.Future[None]) -> None:
    """Retrieve a settled future's exception so the interpreter does not warn at exit.

    取走已设置的异常，避免解释器退出时报告异常未被取用。
    """
    if not future.cancelled():
        future.exception()
