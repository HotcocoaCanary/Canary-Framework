"""Web-extension errors — all inherit :class:`WebError` (which inherits :class:`CanaryError`).

web 扩展的错误：全部继承 :class:`WebError`，而 :class:`WebError` 又继承核心的
:class:`CanaryError`，因此用户 ``except CanaryError`` 即可统一捕获核心与 web 的错误。
"""

from __future__ import annotations

from canary_framework.common.error import CanaryError


class WebError(CanaryError):
    """Base class for every web-extension error.

    web 扩展所有错误的根基类。
    """


class RouteRegistrationError(WebError):
    """Raised when a route cannot be registered (duplicate method + path).

    路由无法注册时抛出（例如同一 method + path 重复声明）。
    """


class MissingParameterError(WebError):
    """Raised when a required request parameter is absent.

    请求缺少必填参数时抛出（内部使用，通常映射为 HTTP 422）。
    """
