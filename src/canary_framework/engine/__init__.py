"""Framework engine — registry, DI injector, hook discovery, and logging."""

from canary_framework.engine.hooks import (
    HookDict,
    LifecycleAware,
    find_hooks,
)
from canary_framework.engine.injector import (
    inject_deps,
    to_snake,
    topological_sort,
)
from canary_framework.engine.logging import get_logger
from canary_framework.engine.registry import Registry
from canary_framework.engine.utils import make_subclass

__all__ = [
    "HookDict",
    "LifecycleAware",
    "Registry",
    "find_hooks",
    "get_logger",
    "inject_deps",
    "make_subclass",
    "to_snake",
    "topological_sort",
]
