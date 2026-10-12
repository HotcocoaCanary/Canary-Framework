"""The server unit: listening is its ``@start``, closing is its ``@stop``.

服务器单元。需要 uvicorn：``pip install canary-framework[server]``::

    from canary_framework.web.asgi.server import Server

    class Gateway(Server):
        api = dep(LibraryApi)           # 一个应用单元，应答 /
        metrics = dep(Metrics)          # 另一个，应答 /metrics

        port = 8010

    async with Gateway():       # 依赖按序启动，最后开始监听
        ...                     # 退出时先停止监听，再逆序回收

它服务的是 ASGI 应用，不问出处：本包的 ``App``、一个 FastAPI 对象、手写的 ASGI 可调用对象
都一样。
"""

from canary_framework.web.asgi.server.server import Server

__all__ = ["Server"]
