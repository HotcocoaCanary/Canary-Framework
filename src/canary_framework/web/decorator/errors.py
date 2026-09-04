"""Exception-mapping decorator — declare how an exception becomes a response.

异常映射装饰器：声明「某类异常出现在请求路径上时，应答成什么样」。仿照
``routes.py``——只 ``setattr`` 打标记、不改造类，因此方法仍可继承 / 混入。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from canary_framework.common.markers import ON_REQUEST_ERROR
from canary_framework.web.error.web import RouteRegistrationError
from canary_framework.web.infra.checks import require_async

_T = TypeVar("_T", bound=Callable[..., object])


def on_request_error(*exc_types: type[Exception]) -> Callable[[_T], _T]:
    """Mark *fn* as the response builder for *exc_types* raised while serving a request.

    把方法标记为这些异常的响应构造器。签名固定为 ``(self, request, exc) -> Response``，
    返回值就是发给客户端的响应，异常到此为止、不再向上传播。用法::

        @web_cocoa(deps=[Repo])
        class API:
            @on_request_error(BookNotFound)
            async def missing(self, request: Request, exc: BookNotFound) -> Response:
                return JSONResponse({"detail": str(exc)}, status_code=404)

    作用域是**全应用**而非单条路由——同一个领域异常在不同端点上映射成不同状态码
    几乎总是 bug 而不是需求，所以所有单元的登记会合并，重复登记同一类型在装配期报错。
    登记内置类型（:class:`RequestValidationError` / :class:`HTTPError` / ``Exception``）
    则是有意支持的：那是把 422 / 500 换成自家错误信封的入口。

    查找按 ``type(exc).__mro__`` 逐级向上，命中最具体的那一个。
    """
    if not exc_types:
        raise RouteRegistrationError("@on_request_error() requires at least one exception type")
    for exc_type in exc_types:
        if not (isinstance(exc_type, type) and issubclass(exc_type, Exception)):
            raise RouteRegistrationError(
                f"@on_request_error() takes exception types, got {exc_type!r}"
            )

    def mark(fn: _T) -> _T:
        names = ", ".join(t.__name__ for t in exc_types)
        require_async(fn, f"the error handler for {names}")
        setattr(fn, ON_REQUEST_ERROR, exc_types)
        return fn

    return mark
