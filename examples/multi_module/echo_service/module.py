"""Module definition for the standalone echo service.

This is the most important demo: a **single ``@service``** decorated with
``@web`` and ``@router`` that can be passed directly to ``WebCanary()``
without any ``@module`` wrapper.  Demonstrates that ``@service`` is the
minimum viable entry point for the framework.

Usage::

    app = WebCanary(EchoService)
    await app.init()
    await app.start()
"""

from __future__ import annotations

from canary_framework import Context, on_end, on_init, on_start, service
from canary_framework.web.fastapi import web
from echo_service.config import EchoConfig
from echo_service.router.echo_router import EchoRouter
from echo_service.service.echo import EchoServiceImpl

__all__ = ["EchoService"]


@web(routers=[EchoRouter])
@service(name="echo_service", config=EchoConfig)
class EchoService:
    """Standalone web service — launched directly via ``WebCanary(EchoService)``.

    A ``@service`` decorated with ``@web(routers=[...])`` is a fully valid
    ``WebCanary`` entry point.  No ``@module`` is needed when you only need
    a single service with HTTP routes.
    """

    def __init__(self) -> None:
        self._impl = EchoServiceImpl()
        self._running = False

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.config_as(EchoConfig)
        self._running = True
        self._greeting = cfg.greeting

    @on_start
    def start(self) -> None:
        self._running = True

    @on_end
    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running
