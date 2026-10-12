"""The FastAPI application unit.

FastAPI 应用单元：沿依赖图挂好路由，自己不监听。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from fastapi import FastAPI

from canary_framework import asgi
from canary_framework.asgi.fastapi.router import mount
from canary_framework.core import init


class App(asgi.App):
    """A unit that is a FastAPI app built from the routers it depends on.

    FastAPI 应用单元。类参数原样传给 FastAPI::

        class LibraryApi(App, title="图书馆 API", version="1.0.0"):
            readers = dep(ReaderApi)
            loans = dep(LoanApi)

            @init
            def setup(self) -> None:
                self.app.add_exception_handler(DomainError, self.on_domain_error)

        class Gateway(asgi.Server):
            api = dep(LibraryApi)
            port = 8010

    ``@init`` 建出 FastAPI 应用 :attr:`app`，挂上自己的接口与它直接依赖的路由单元。子类的
    ``@init`` 在此之后运行，可以继续配置 :attr:`app`——此时还没有开始服务，中间件与异常
    处理器都来得及。

    它自己不监听：哪个 :class:`canary_framework.asgi.Server` 直接依赖它，它就在那个端口上。
    一个进程通常只需要一个，所以 OpenAPI 文档也只有一份。

    :param options: 原样传给 ``FastAPI(...)`` 的参数（``title``、``version``、``docs_url``
        ……）。子类继承父类的全部类参数，只覆盖自己写出的那些。
    """

    #: FastAPI 应用，``@init`` 之后可用。
    app: FastAPI

    #: 本类的类参数，原样传给 ``FastAPI``。
    __canary_app__: ClassVar[Mapping[str, Any]] = {}

    def __init_subclass__(cls, **options: Any) -> None:
        super().__init_subclass__()
        cls.__canary_app__ = {**cls.__canary_app__, **options}

    @init
    def _assemble(self) -> None:
        self.app = FastAPI(**self.__canary_app__)
        mount(self, self.app)
