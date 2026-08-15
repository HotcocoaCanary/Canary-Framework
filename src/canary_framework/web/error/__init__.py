"""Web-extension errors.

web 扩展的错误体系：:class:`WebError` 及其子类。
"""

from canary_framework.web.error.web import (
    MissingParameterError,
    RouteRegistrationError,
    WebError,
)

__all__ = ["MissingParameterError", "RouteRegistrationError", "WebError"]
