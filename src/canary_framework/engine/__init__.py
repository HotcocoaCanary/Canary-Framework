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
from canary_framework.engine.logging import (
    get_logger,
    init_logging,
    sanitize_config_values,
)
from canary_framework.engine.registry import Registry

__all__ = [
    "HookDict",
    "LifecycleAware",
    "Registry",
    "find_hooks",
    "get_logger",
    "init_logging",
    "inject_deps",
    "sanitize_config_values",
    "to_snake",
    "topological_sort",
]
