"""Entry point — launch the full AppModule via WebCanary.

Usage:
    uv run python run_app.py

Registers:
    - NotifyService        (standalone, no deps)
    - UserModule           (auth + user services, user CRUD router)
    - BlogServiceModule    (blog service, depends on notify + user)

Endpoints:
    GET  http://127.0.0.1:8000/api/health
    GET  http://127.0.0.1:8000/api/users/
    GET  http://127.0.0.1:8000/api/users/{id}
    POST http://127.0.0.1:8000/api/users/
    DELETE http://127.0.0.1:8000/api/users/{id}
    GET  http://127.0.0.1:8000/api/blog/
    GET  http://127.0.0.1:8000/api/blog/{id}
    POST http://127.0.0.1:8000/api/blog/
    PUT  http://127.0.0.1:8000/api/blog/{id}
    PATCH http://127.0.0.1:8000/api/blog/{id}
    GET  http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import asyncio
import signal
import sys

from app_module.module import AppModule

from canary_framework.web.fastapi import WebCanary


async def main() -> None:
    print("Starting AppModule via WebCanary on http://127.0.0.1:8000 ...")
    print("Press Ctrl+C to stop.\n")
    app = WebCanary(AppModule)
    await app.init()
    await app.start()


# Allow clean shutdown on Ctrl+C
def _shutdown(signum: int, frame: object) -> None:
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    asyncio.run(main())
