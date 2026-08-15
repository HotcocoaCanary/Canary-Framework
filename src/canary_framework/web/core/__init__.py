"""Web core — the app builder and the ``@web_cocoa`` decorator.

核心：``@web_cocoa`` 标记 + 服务入口构建（``build_web_app``），以及请求分发和 OpenAPI
文档生成。
"""

from canary_framework.web.core.app import build_web_app
from canary_framework.web.core.extension import web_cocoa
from canary_framework.web.core.openapi import build_openapi
from canary_framework.web.core.routing import dispatch

__all__ = ["build_openapi", "build_web_app", "dispatch", "web_cocoa"]
