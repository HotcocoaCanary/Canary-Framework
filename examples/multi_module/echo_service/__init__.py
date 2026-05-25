"""Echo service — standalone ``@service`` with ``@web`` router.

Demonstrates that a single ``@service`` can be directly passed to
``WebCanary()`` — no ``@module`` wrapper required.
"""

from __future__ import annotations

from echo_service.config import EchoConfig
from echo_service.module import EchoService as EchoService

__all__ = ["EchoConfig", "EchoService"]
