"""Entry point — launch the standalone EchoService via WebCanary directly.

Usage:
    uv run python run_standalone_web.py

A single ``@service`` with a ``@router``-decorated class in ``deps=`` can
be passed directly to ``WebCanary()`` — no ``@module`` wrapper needed.

This is the simplest possible web entry point in the Canary Framework.

Endpoints:
    GET  http://127.0.0.1:8001/echo/
    GET  http://127.0.0.1:8001/echo/{text}
    POST http://127.0.0.1:8001/echo/
    GET  http://127.0.0.1:8001/docs
"""

from __future__ import annotations

import asyncio
import signal
import sys

from echo_service.module import EchoService

from canary_framework.web.fastapi import WebCanary


async def main() -> None:
    print("Starting standalone EchoService via WebCanary on http://127.0.0.1:8001 ...")
    print("Press Ctrl+C to stop.\n")
    app = WebCanary(EchoService)
    await app.init()
    await app.start()


def _shutdown(signum: int, frame: object) -> None:
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    asyncio.run(main())
