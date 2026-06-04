"""Framework engine — registry, hook discovery, logging, and OpenAPI."""

from canary_framework.engine.injector import topological_sort
from canary_framework.engine.logging import ensure_logging, get_logger
from canary_framework.engine.registry import Registry

__all__ = [
    "Registry",
    "ensure_logging",
    "get_logger",
    "topological_sort",
]
