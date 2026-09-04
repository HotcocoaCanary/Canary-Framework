"""Web-extension errors — all inherit :class:`WebError` (which inherits :class:`CanaryError`).

web 扩展的错误：全部继承 :class:`WebError`，而 :class:`WebError` 又继承核心的
:class:`CanaryError`，因此用户 ``except CanaryError`` 即可统一捕获核心与 web 的错误。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

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


class HTTPError(WebError):
    """An error that already knows its own HTTP response.

    HTTP 语义自带的错误：``raise HTTPError(401, "token expired")``。内置处理器把它
    变成 ``{"detail": ...}``，无需登记 ``@on_request_error``。领域错误不该继承它——
    那会让领域层知道 HTTP 的存在；领域错误用 ``@on_request_error`` 映射。
    """

    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail if detail is not None else "HTTP error"
        self.headers = headers
        super().__init__(f"{status_code}: {self.detail}")


class RequestValidationError(WebError):
    """Raised when a request cannot be bound to the handler's signature.

    请求无法绑定到 handler 签名时抛出（缺参 / 校验失败），内置处理器映射为 422。
    它被设计成**可抛出、可拦截**的，因此使用者可以用
    ``@on_request_error(RequestValidationError)`` 把 422 改成自家的错误信封。
    """

    def __init__(self, cause: ValidationError | MissingParameterError) -> None:
        self.cause = cause
        super().__init__(str(cause))

    @property
    def detail(self) -> Any:
        """The error payload: pydantic's error list, or a plain message."""
        if isinstance(self.cause, ValidationError):
            # 走 .json() 而不是 .errors()：后者的 ctx 里可能挂着 validator 抛出的活异常
            # 对象，直接塞进 JSONResponse 会让 422 自身崩成 500。pydantic 的 json()
            # 已做好脱敏，且保留了 gt / max_length 这类有用的约束值。
            return json.loads(self.cause.json(include_url=False))
        return str(self.cause)
