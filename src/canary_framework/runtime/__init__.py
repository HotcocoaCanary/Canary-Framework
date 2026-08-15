"""The runtime engine — :class:`Canary` and the graph algorithms.

运行时引擎：编排器 :class:`Canary` 与图算法。核心包（``core``）保留声明层原语
（装饰器 / 命名 / 标记）；服务入口由各单元在 ``start()`` 阶段暴露，``Canary`` 按
鸭子类型委托给它们，不 import 任何具体扩展。
"""

from canary_framework.runtime.canary import Canary
from canary_framework.runtime.graph import build_graph, topological_sort

__all__ = [
    "Canary",
    "build_graph",
    "topological_sort",
]
