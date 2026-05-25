"""Module definition for the standalone notification service.

This is the simplest form of a Canary Framework service: a single
``@service`` class with configuration and lifecycle hooks, no dependencies.
"""

from __future__ import annotations

from canary_framework import Context, on_end, on_init, on_start, service
from standalone.config import NotifyConfig
from standalone.service.notify import NotifyService as _NotifyImpl

__all__ = ["NotifyService"]


@service(name="notify", config=NotifyConfig)
class NotifyService:
    """Notification service — sends notifications via the configured provider."""

    def __init__(self) -> None:
        self._impl = _NotifyImpl()
        self._started = False

    @on_init
    def init(self, ctx: Context) -> None:
        cfg = ctx.config_as(NotifyConfig)
        if not cfg.enabled:
            return
        self._impl.send("system", f"NotifyService initialised (provider={cfg.provider})")

    @on_start
    def start(self) -> None:
        self._started = True
        self._impl.send("system", "NotifyService started")

    @on_end
    def stop(self) -> None:
        self._started = False
        self._impl.send("system", "NotifyService stopped")

    # ── public API ──

    def notify(self, recipient: str, message: str) -> str:
        return self._impl.send(recipient, message)

    @property
    def started(self) -> bool:
        return self._started

    @property
    def history(self) -> list[str]:
        return self._impl.history
