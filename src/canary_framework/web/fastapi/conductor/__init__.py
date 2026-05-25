"""FastAPI conductor — Web engine for FastAPI integration.

Provides :class:`WebCanary`, which extends :class:`~canary_framework.core.conductor.canary.Canary`
to boot a FastAPI + Uvicorn server.
"""

from canary_framework.web.fastapi.conductor.web_canary import WebCanary

__all__ = ["WebCanary"]
