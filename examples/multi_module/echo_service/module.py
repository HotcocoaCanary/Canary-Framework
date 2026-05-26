"""Module definition for the standalone echo service.

A single ``@service`` with its router declared in ``deps`` can be passed
directly to ``WebCanary()`` without any ``@module`` wrapper.

Usage::

    app = WebCanary(EchoService)
    await app.init()
    await app.start()
"""

from __future__ import annotations

from canary_framework import Context, on_end, on_init, on_start, service
from echo_service.config import EchoConfig
from echo_service.router.echo_router import EchoRouter
from echo_service.service.echo import EchoServiceImpl

__all__ = ["EchoService"]


@service(name="echo_service", config=EchoConfig, deps=[EchoRouter])
class EchoService:
    """Standalone web service — launched directly via ``WebCanary(EchoService)``.

    The ``@router``-decorated ``EchoRouter`` is declared in ``deps=``,
    so the framework auto-discovers and initialises it.  No ``@module``
    wrapper is needed for single-service web deployments.
    """

    def __init__(self) -> None:
        self._impl = EchoServiceImpl()
        self._running = False

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.get_config(EchoConfig)
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
