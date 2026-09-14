"""Calling one hook.

调用一个钩子。按返回值而非函数声明判断是否需要 ``await``，因此同时覆盖 ``async def``
与返回协程的同步函数。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable


async def invoke(hook: Callable[[], object]) -> None:
    """Run *hook*, awaiting the result when it is awaitable.

    调用 *hook*，返回值可等待时 ``await`` 它。
    """
    result = hook()
    if inspect.isawaitable(result):
        await result
