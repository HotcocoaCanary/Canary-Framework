"""ASGI: applications and servers that are units, and compatible with everything else.

ASGI。协议的两侧各是一个子包，都是单元，也都只认协议本身：

- ``canary_framework.web.asgi.app`` —— 应用单元。它自己就是一个 ASGI 应用，可以交给任何
  ASGI 服务器（本包的 ``Server``、uvicorn、hypercorn ……）。
- ``canary_framework.web.asgi.server`` —— 服务器单元。它监听一个端口，服务任何 ASGI 应用
  （本包的 ``App``、FastAPI、Starlette、手写的 ``async def app(scope, receive, send)`` ……）。

两个子包互不依赖，各自只依赖这一层：:data:`Application` 是 ASGI 应用的类型，
:func:`dispatch` 把若干应用按路径前缀合成一个。
"""

from canary_framework.web.asgi.protocol import Application, dispatch

__all__ = ["Application", "dispatch"]
