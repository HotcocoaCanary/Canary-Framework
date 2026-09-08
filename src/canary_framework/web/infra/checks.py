"""Declaration-time checks shared by the web decorators.

装配期检查：装饰器在打标记之前先把关，错误在 import 那一刻就报出来，而不是等到线上。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable

from canary_framework.web.decorator.params import Param
from canary_framework.web.error.web import RouteRegistrationError


def require_async(fn: Callable[..., object], subject: str) -> None:
    """Refuse to register a blocking callable on the request path.

    同步函数会在事件循环线程上运行，阻塞的不是它自己那个请求，而是整个进程——同一
    时刻所有路由、所有后台任务一起停摆。框架不替使用者把它偷偷挪进线程池（那会让
    “这段代码跑在哪儿”变成隐式的），而是在装配期直接拒绝。

    阻塞调用请显式让出：``await asyncio.to_thread(blocking_call, ...)``。它是标准库、
    一行、写在哪儿就在哪儿生效——handler、仓储、生命周期钩子里都是同一种写法。
    """
    if inspect.iscoroutinefunction(fn):
        return
    where = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
    raise RouteRegistrationError(
        f"{where} is registered as {subject} but is not an async function. "
        f"Canary runs the request path on the event loop and never offloads silently — "
        f"a blocking call here stalls the whole process, not just its own request. "
        f"Declare it 'async def' and wrap blocking calls with 'await asyncio.to_thread(...)'."
    )


def require_annotated_sources(fn: Callable[..., object], subject: str) -> None:
    """Refuse a source marker written as a default value.

    ``Annotated[str, Header()]`` 和 ``str = Header()`` 说的是同一件事，但后者让"默认值"
    这个位置同时表示两件事——既是来源标记又是缺省取值。框架只认前者，并且在装配期就说
    出来：留着后者的话，标记对象会被当成真正的默认值发给客户端。
    """
    for name, param in inspect.signature(fn).parameters.items():
        if not isinstance(param.default, Param):
            continue
        marker = type(param.default).__name__
        where = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
        raise RouteRegistrationError(
            f"{where} is registered as {subject}, but parameter '{name}' uses "
            f"'{name}: T = {marker}(...)'. Source markers go in the annotation: "
            f"'{name}: Annotated[T, {marker}(...)]', with the default value where "
            f"defaults belong ('= ...')."
        )
