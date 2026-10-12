"""ASGI applications as units, and the server that listens for them.

ASGI。需要 uvicorn：``pip install canary-framework[asgi]``::

    class Gateway(Server):
        api = dep(LibraryApi)           # 一个应用单元，应答 /
        metrics = dep(Metrics)          # 另一个，应答 /metrics

        port = 8010

    async with Gateway():       # 依赖按序启动，最后开始监听
        ...                     # 退出时先停止监听，再逆序回收

三个角色分开：

- :class:`App` 是应用单元——一个 ASGI 应用，自己不监听。``canary_framework.asgi.fastapi`` 的
  ``App`` 就是一个。
- :class:`Server` 是监听的单元——每个端口一个，服务它直接依赖的应用单元。
- :func:`dispatch` 把若干 ASGI 应用按路径前缀合成一个，供需要手动拼装时使用。

依赖方向严格单向：``server -> app``。
"""

from canary_framework.asgi.app import App, Application, dispatch
from canary_framework.asgi.server import Server

__all__ = ["App", "Application", "Server", "dispatch"]
