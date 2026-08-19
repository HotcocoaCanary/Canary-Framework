"""Mount points — where each web unit's routes hang on the dependency graph.

挂载点：纯图算法，沿依赖边把 ``prefix`` 逐级拼接，算出每个 web 单元的挂载前缀。

规则只有一条——**实例共享，挂载不共享**：依赖图上每个类型仍然只有一个实例，但它的
路由挂在“依赖路径”上；同一个单元被两条路径依赖，就在两处各挂一份::

    A(prefix="/a", deps=[B, C])
    B(prefix="/b", deps=[C])
    C(prefix="/c")

    → A: ["/a"]  B: ["/a/b"]  C: ["/a/b/c", "/a/c"]

链路中间的非 web 单元不贡献前缀，直接跳过（``A -> Repo -> C`` 与 ``A -> C`` 同义）。
"""

from __future__ import annotations

from canary_framework.common.markers import WEB_ATTR
from canary_framework.core.decorator.introspect import deps_of


def mount_prefixes(
    roots: tuple[type, ...] | list[type], graph: dict[type, object]
) -> dict[type, list[str]]:
    """Return each web type's mount prefixes, in root-first depth-first order.

    从每个根出发深度优先遍历依赖图，遇到 web 单元就把它的 ``prefix`` 接在当前前缀
    之后并记一次挂载。``(类型, 前缀)`` 组合只走一次——同一条前缀重复到达时子树的结果
    必然相同，剪掉既能去重也能防止菱形依赖下的路径爆炸。

    返回值按“根在前”的遍历顺序排列，调用方可据此取最外层单元的文档元数据。
    """
    mounts: dict[type, list[str]] = {}
    visited: set[tuple[type, str]] = set()

    def visit(t: type, prefix: str) -> None:
        if (t, prefix) in visited:
            return
        visited.add((t, prefix))
        meta: dict[str, str] | None = getattr(t, WEB_ATTR, None)
        if meta is not None:
            prefix = join_prefix(prefix, meta.get("prefix", ""))
            mounts.setdefault(t, []).append(prefix)
        for dep in deps_of(t):
            if dep in graph:
                visit(dep, prefix)

    for root in roots:
        visit(root, "")
    return mounts


def join_prefix(base: str, prefix: str) -> str:
    """Chain a nested unit's *prefix* onto its ancestor's *base*.

    与路由级拼接不同：这里两端都可能为空，且结果永不带尾部 ``/``——它还要继续和
    下一级前缀或路由路径拼接。
    """
    base = base.rstrip("/")
    prefix = prefix.strip("/")
    return f"{base}/{prefix}" if prefix else base


def join_path(prefix: str, path: str) -> str:
    """Join a mount *prefix* with a route-level *path*.

    与 :func:`join_prefix` 的区别：这是最后一级拼接，路由自身的 ``/`` 要保留——
    ``prefix="/api"`` 加上 ``@get("/")`` 得到 ``/api/``，而不是 ``/api``。
    """
    prefix = prefix.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return prefix + path if prefix else path
