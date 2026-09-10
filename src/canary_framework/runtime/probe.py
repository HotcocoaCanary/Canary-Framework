"""The framework's own two knobs, read straight from the environment.

框架自有的两个开关，改的是进程级状态（``canary`` logger 树的级别、事件循环的调试标志），
与图无关，故单独成模块。
"""

from __future__ import annotations

import asyncio
import logging
import os

from canary_framework.common.error import LifecycleError

# 探针改动前的旧值：(loop, 原 debug 标志, 原 slow_callback_duration)。
type ProbeState = tuple[asyncio.AbstractEventLoop, bool, float] | None


async def apply_probe(current: ProbeState) -> ProbeState:
    """Apply the ``CANARY_*`` settings; return what has to be restored later.

    读环境变量并生效，返回停止时需要还原的旧值（未开探针时为 ``None``）。

    ``CANARY_LOG_LEVEL`` 只设置 ``canary`` 这一棵 logger 的级别：不装 handler、不设
    format、不碰 root；未设置时不做任何干预。

    ``CANARY_SLOW_CALLBACK_SECONDS`` 打开事件循环延迟探针：占用事件循环超过该秒数的回调
    会被 asyncio 记一条 WARNING，``async def`` 函数体里的同步阻塞同样会被抓到。它会打开
    asyncio 的调试模式并带来额外开销，属开发期工具，默认关闭。

    :raises LifecycleError: ``CANARY_SLOW_CALLBACK_SECONDS`` 不是一个数字。
    """
    level = os.environ.get("CANARY_LOG_LEVEL")
    if level:
        logging.getLogger("canary").setLevel(level.upper())

    raw = os.environ.get("CANARY_SLOW_CALLBACK_SECONDS")
    if not raw:
        return current
    try:
        seconds = float(raw)
    except ValueError as exc:
        raise LifecycleError(
            f"CANARY_SLOW_CALLBACK_SECONDS must be a number of seconds, got {raw!r}"
        ) from exc
    loop = asyncio.get_running_loop()
    # 调试模式是事件循环的全局状态，停止时必须还原，否则会影响同进程的后续代码。
    state: ProbeState = (loop, loop.get_debug(), loop.slow_callback_duration)
    loop.set_debug(True)
    loop.slow_callback_duration = seconds
    # asyncio 在回调开始执行前才读 loop._debug，而这里是在回调执行途中才打开它，
    # 因此必须让出一次，剩余的启动才会落在被计时的新回调里。
    await asyncio.sleep(0)
    return state


def restore_probe(state: ProbeState) -> ProbeState:
    """Put the event loop back the way it was. 还原，并返回新的（空）状态。"""
    if state is None:
        return None
    loop, debug, duration = state
    loop.set_debug(debug)
    loop.slow_callback_duration = duration
    return None
