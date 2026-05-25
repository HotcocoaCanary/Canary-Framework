"""Business-logic implementation of the notification service.

The framing ``@service`` class (see :mod:`standalone.module`) receives
dependency injection and lifecycle hooks, then delegates to this class
for the actual notification logic.
"""

from __future__ import annotations


class NotifyService:
    """Pure business logic for sending notifications."""

    def __init__(self) -> None:
        self._sent: list[str] = []

    def send(self, recipient: str, message: str) -> str:
        record = f"to={recipient} msg={message}"
        self._sent.append(record)
        return record

    @property
    def history(self) -> list[str]:
        return list(self._sent)
