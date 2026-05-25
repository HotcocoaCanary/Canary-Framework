"""Pure business logic for the echo service."""

from __future__ import annotations


class EchoServiceImpl:
    """Processes and echoes messages."""

    def process(self, message: str, prefix: str = "") -> str:
        if prefix:
            return f"{prefix} {message}"
        return message
