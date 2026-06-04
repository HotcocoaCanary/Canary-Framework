"""Framework engine — registry, hook discovery, logging, and OpenAPI."""

from canary_framework.common.types import LifecycleAware
from canary_framework.engine.hooks import (
    HookDict,
    find_hooks,
)
from canary_framework.engine.injector import topological_sort
from canary_framework.engine.logging import ensure_logging, get_logger
from canary_framework.engine.openapi import generate_openapi_schema
from canary_framework.engine.registry import Registry
from canary_framework.engine.utils import make_subclass

__all__ = [
    "HookDict",
    "LifecycleAware",
    "Registry",
    "ensure_logging",
    "find_hooks",
    "generate_openapi_schema",
    "get_logger",
    "make_subclass",
    "topological_sort",
]
