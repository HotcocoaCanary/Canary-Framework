"""Core module — decorators, conductor, and algorithms.

Public API:
    - Decorators:  :func:`service`, :func:`module`,
      :func:`on_config`, :func:`on_init`, :func:`on_start`, :func:`on_end`
    - Conductor:   :class:`Canary`
"""

from canary_framework.core.conductor import Canary
from canary_framework.core.decorators.lifecycle import (
    on_config,
    on_end,
    on_init,
    on_start,
)
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service

__all__ = [
    "Canary",
    "module",
    "on_config",
    "on_end",
    "on_init",
    "on_start",
    "service",
]
