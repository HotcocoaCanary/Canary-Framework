"""The assembly summary — what the runtime actually built, said out loud.

装配摘要：框架掌握着全部事实（启动顺序、每个单元的依赖），却一直零输出。这里在 DEBUG
级别一次性说清楚，排查"为什么这个单元先启动"时不必去读框架源码。

它是**诊断**，不是引擎——所以不在 ``canary.py`` 里。纯函数，接收已经装配好的图，返回一段
文本；不碰状态，也不做任何决定。
"""

from __future__ import annotations

from canary_framework.core.decorator.introspect import deps_of


def assembly_summary(roots: tuple[type, ...], order: list[type]) -> str:
    """Render the start order and each unit's dependencies.

    渲染启动顺序与逐个单元的依赖。多根时补一句提醒：那种情况下没有任何单元最后启动，
    也就不存在"一切都起来之后"那个位置。
    """
    lines = [f"Canary assembled {len(order)} unit(s)"]
    lines.append("  roots: " + ", ".join(r.__name__ for r in roots))
    if len(roots) > 1:
        lines.append(
            "  note: with multiple roots no unit starts last, so there is no "
            "'after everything started' position; declare one composition root if you need it"
        )
    lines.append("  start order (stop runs in reverse):")
    for i, t in enumerate(order, 1):
        deps = ", ".join(d.__name__ for d in deps_of(t))
        lines.append(f"    {i}. {t.__name__}" + (f"  <- {deps}" if deps else ""))
    return "\n".join(lines)
