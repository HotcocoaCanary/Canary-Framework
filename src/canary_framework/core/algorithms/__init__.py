"""Algorithms — injector, sorter, and naming utilities."""

from canary_framework.core.algorithms.injector import inject_deps
from canary_framework.core.algorithms.naming import to_snake
from canary_framework.core.algorithms.sorter import topological_sort

__all__ = [
    "inject_deps",
    "to_snake",
    "topological_sort",
]
