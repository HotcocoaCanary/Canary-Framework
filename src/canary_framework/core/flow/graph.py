"""The dependency graph of one scope.

依赖图：节点是单元在作用域内的键，边来自 ``dep()`` 声明，并按 :meth:`Scope.provide` 的替换
解析。图是静态的——``dep()`` 是类上的声明，替换只能在生命周期开始之前登记——因此一个节点
第一次被进入时，连同它的全部依赖一起加入，此后不再变化。

环在加入时检测，早于任何钩子运行。节点在它的依赖全部加入之后才加入，因此
``scope.graph`` 的插入顺序本身就是一个拓扑序：依赖在前，依赖者在后。
"""

from __future__ import annotations

from collections.abc import Iterator

from canary_framework.core.errors import CircularDependencyError
from canary_framework.core.flow.scope import Scope
from canary_framework.core.meta.introspect import deps_of


def include(scope: Scope, root: type) -> None:
    """Add *root* and everything it depends on to *scope*'s graph.

    把 *root* 及其全部依赖加入依赖图。迭代的深度优先遍历，不受递归上限约束；依赖按声明
    顺序访问，因此互不依赖的单元按声明顺序排列。发现环时抛出，且不改动已有的图。

    :raises CircularDependencyError: 依赖成环，异常携带从 *root* 出发走到环上的路径。
    """
    graph = scope.graph
    if root in graph:
        return
    found: dict[type, tuple[type, ...]] = {}
    path: list[type] = []
    on_path: set[type] = set()  # 与 path 同步，成员判断不随深度变慢
    stack: list[tuple[type, Iterator[type]]] = []

    def visit(cls: type) -> None:
        found[cls] = deps_of(scope.resolve(cls))
        path.append(cls)
        on_path.add(cls)
        stack.append((cls, iter(found[cls])))

    visit(root)
    added: dict[type, None] = {}  # 有序集合：插入顺序即后序，依赖先于依赖者
    while stack:
        cls, pending = stack[-1]
        for dependency in pending:
            if dependency in graph or dependency in added:
                continue
            if dependency in on_path:
                raise CircularDependencyError((*path, dependency))
            visit(dependency)
            break
        else:
            stack.pop()
            on_path.discard(path.pop())
            added[cls] = None
    for cls in added:
        graph[cls] = found[cls]
        for dependency in found[cls]:
            scope.dependents.setdefault(dependency, []).append(cls)


def closure(scope: Scope, root: type) -> list[type]:
    """Return *root* and everything it depends on, in topological order (dependencies first).

    返回 *root* 及其全部依赖，依赖在前。*root* 须已加入依赖图。
    """
    reached: set[type] = set()
    todo = [root]
    while todo:
        cls = todo.pop()
        if cls not in reached:
            reached.add(cls)
            todo.extend(scope.graph[cls])
    return [cls for cls in scope.graph if cls in reached]
