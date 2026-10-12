"""Route marks: FastAPI's own decorators, recorded.

路由标记。名字、参数与默认值都是 FastAPI ``APIRouter`` 同名方法的——``@get(...)`` 只是把这次
调用记在方法上，不改造方法，也不注册任何东西。把它原样重放到真正的 ``APIRouter`` 上的是
``router.mount``。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Concatenate, Protocol

from fastapi import APIRouter

#: 写在方法上的标记：该方法是哪些接口，值为 :class:`Route` 的元组。
ROUTES = "__canary_routes__"


@dataclass(frozen=True, slots=True)
class Route:
    """One recorded call: which ``APIRouter`` method, and with what arguments.

    一次被记下的调用：``APIRouter`` 的哪个方法，带着什么参数。
    """

    verb: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


class _Mark(Protocol):
    def __call__[F: Callable[..., object]](self, fn: F, /) -> F: ...


def _record[**P](method: Callable[Concatenate[APIRouter, P], Any]) -> Callable[P, _Mark]:
    """把 ``APIRouter`` 的一个装饰器方法变成同名、同签名的标记。"""
    verb = method.__name__

    def mark(*args: P.args, **kwargs: P.kwargs) -> _Mark:
        if args and not isinstance(args[0], str):
            raise TypeError(f"@{verb} takes a path, as FastAPI's does: @{verb}('/')")
        route = Route(verb, args, dict(kwargs))

        def apply[F: Callable[..., object]](fn: F, /) -> F:
            setattr(fn, ROUTES, (*getattr(fn, ROUTES, ()), route))
            return fn

        return apply

    mark.__name__ = mark.__qualname__ = verb
    native = inspect.signature(method)
    # 运行时看到的签名也是 FastAPI 的（去掉 self），help() 与文档工具因此照常可用。
    mark.__signature__ = native.replace(  # type: ignore[attr-defined]
        parameters=list(native.parameters.values())[1:]
    )
    mark.__doc__ = (
        f"Mark a unit's method as an endpoint; the arguments are those of FastAPI's "
        f"``APIRouter.{verb}``.\n\n把单元的方法标记为接口，参数与 FastAPI 的 "
        f"``APIRouter.{verb}`` 完全相同::\n\n"
        f'    @{verb}("/{{reader_id}}")\n'
        f"    async def show(self, reader_id: int) -> Reader: ...\n\n"
        f"同一个方法可以带多个标记。\n"
    )
    return mark


get = _record(APIRouter.get)
post = _record(APIRouter.post)
put = _record(APIRouter.put)
patch = _record(APIRouter.patch)
delete = _record(APIRouter.delete)
head = _record(APIRouter.head)
options = _record(APIRouter.options)
trace = _record(APIRouter.trace)
api_route = _record(APIRouter.api_route)
websocket = _record(APIRouter.websocket)


def routes_of(unit: object) -> list[tuple[Route, Callable[..., object]]]:
    """Return *unit*'s marked methods, bound, with their marks — base classes first.

    返回 *unit* 上带标记的绑定方法及其标记，基类在前，同一个类内按定义顺序。

    与生命周期钩子一样按**属性名**解析：子类覆盖同名方法即替换；覆盖但不再标记时，它不再
    是接口。
    """
    names: dict[str, None] = {}
    for klass in reversed(type(unit).__mro__):
        for name, value in vars(klass).items():
            if hasattr(value, ROUTES):
                names[name] = None
    found: list[tuple[Route, Callable[..., object]]] = []
    for name in names:
        bound = getattr(unit, name)
        found.extend((route, bound) for route in getattr(bound, ROUTES, ()))
    return found
