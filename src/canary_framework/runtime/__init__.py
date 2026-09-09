"""The runtime engine — assembly, lifecycle, and the pieces around them.

运行时：装配与生命周期。四个模块各管一件事——

- :mod:`~canary_framework.runtime.canary` 引擎本身（:class:`Canary`）
- :mod:`~canary_framework.runtime.graph`  纯图算法（建图、拓扑排序）
- :mod:`~canary_framework.runtime.probe`  框架自有的两个环境变量开关
- :mod:`~canary_framework.runtime.report` 装配摘要（诊断，不是引擎）
"""

from canary_framework.runtime.canary import Canary
from canary_framework.runtime.graph import build_graph, topological_sort

__all__ = [
    "Canary",
    "build_graph",
    "topological_sort",
]
