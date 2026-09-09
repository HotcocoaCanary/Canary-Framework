"""The framework's own two knobs, read straight from the environment.

框架自有的两个开关。它们和"装配这张图"没有关系——改的是**进程级**的东西（``canary``
这棵 logger 的级别、事件循环的调试标志），所以单独成模块，不混在引擎里。

框架不提供配置机制，也就不该为自己的两个字段引进一个：配置是使用者自己的一个 ``@cocoa``，
日志是标准库的 ``logging``。这两个开关直接读环境变量。
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

    读环境变量并生效，返回停止时需要还原的旧值（没开探针时是 ``None``）。

    ``CANARY_LOG_LEVEL`` 只动 ``canary`` 这一棵 logger 的级别：不装 handler、不设 format、
    不碰 root。未设置时框架完全不干预。

    ``CANARY_SLOW_CALLBACK_SECONDS`` 打开事件循环延迟探针：任何一次占用事件循环超过该秒数
    的回调都会被 asyncio 记一条 WARNING。它抓的是**运行期实际发生的阻塞**——``async def``
    的函数体里调同步驱动同样会被抓到。默认关闭：它会打开 asyncio 的调试模式，有额外开销，
    属于开发期工具。
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
    # 调试模式是整个事件循环的全局状态，停止时必须还原——否则一个开了探针的应用会污染
    # 同进程后续所有代码。
    state: ProbeState = (loop, loop.get_debug(), loop.slow_callback_duration)
    loop.set_debug(True)
    loop.slow_callback_duration = seconds
    # 让出一次，否则整个启动期都测不到：asyncio 在回调**开始执行之前**就读过 loop._debug，
    # 而我们是在这个回调执行到一半时才把它打开的。让出之后，剩下的启动落在新的回调里。
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
