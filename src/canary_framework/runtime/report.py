"""The assembly summary — what the runtime built, how long it took, and what would speed it up.

装配摘要：渲染启动顺序、逐单元依赖与耗时，并在值得时给出并发建议。纯函数，接收已装配好的
图与一份耗时记录，返回一段文本，不碰任何状态。
"""

from __future__ import annotations

from canary_framework.core.decorator.introspect import deps_of

# 低于这个耗时不提并发建议：几毫秒的启动，省下来的比日志本身还不值钱。
_WORTH_SUGGESTING_MS = 20.0
# 加速比低于这个也不提：图太"窄"，并发帮不上忙。
_WORTH_SUGGESTING_SPEEDUP = 1.3


def assembly_summary(
    roots: tuple[type, ...],
    order: list[type],
    timings: dict[type, float] | None = None,
    elapsed_ms: float | None = None,
    concurrency: int | None = None,
) -> str:
    """Render the start order, each unit's dependencies, and a concurrency hint when it pays.

    渲染启动顺序与逐个单元的依赖。多根时补一句提醒：那种情况下没有任何单元最后启动，
    也就不存在"一切都起来之后"那个位置。
    """
    lines = [f"Canary assembled {len(order)} unit(s)"]
    if elapsed_ms is not None:
        lines[0] += f", started in {elapsed_ms:.0f}ms"
    lines.append("  roots: " + ", ".join(r.__name__ for r in roots))
    if len(roots) > 1:
        lines.append(
            "  note: with multiple roots no unit starts last, so there is no "
            "'after everything started' position; declare one composition root if you need it"
        )
    lines.append("  start order (stop runs in reverse):")
    for i, t in enumerate(order, 1):
        deps = ", ".join(d.__name__ for d in deps_of(t))
        cost = f"  [{timings[t]:.0f}ms]" if timings and t in timings else ""
        lines.append(f"    {i}. {t.__name__}" + (f"  <- {deps}" if deps else "") + cost)
    if concurrency is None and timings:
        lines.extend(_concurrency_hint(order, timings))
    return "\n".join(lines)


def _concurrency_hint(order: list[type], timings: dict[type, float]) -> list[str]:
    """Say what ``start_concurrency`` would buy, but only when it is worth saying.

    并发启动的下限是关键路径（按耗时算最长的一条依赖链）；顺序启动付的是所有单元之和，
    两者之差即可省下的时间。建议的并发数取最宽一层的单元数。
    """
    total = sum(timings.values())
    if total < _WORTH_SUGGESTING_MS:
        return []
    longest = _critical_path(order, timings)
    if longest <= 0 or total / longest < _WORTH_SUGGESTING_SPEEDUP:
        return []
    width = max(1, _max_width(order, timings))
    return [
        f"  critical path is {longest:.0f}ms of the {total:.0f}ms spent starting units",
        f"  start_concurrency={width} could bring that down to about {longest:.0f}ms "
        f"({total / longest:.1f}x) — independent units would start together",
    ]


def _critical_path(order: list[type], timings: dict[type, float]) -> float:
    """最长的一条依赖链（按耗时算）。``order`` 是拓扑序，所以一遍就能算完。"""
    longest: dict[type, float] = {}
    for t in order:
        longest[t] = timings.get(t, 0.0) + max((longest[d] for d in deps_of(t)), default=0.0)
    return max(longest.values(), default=0.0)


def _max_width(order: list[type], timings: dict[type, float]) -> int:
    """按拓扑层次估算最宽的一层——够用的并发上限建议值。"""
    depth: dict[type, int] = {}
    for t in order:
        depth[t] = 1 + max((depth[d] for d in deps_of(t)), default=-1)
    counts: dict[int, int] = {}
    for t in order:
        if timings.get(t, 0.0) > 0:
            counts[depth[t]] = counts.get(depth[t], 0) + 1
    return max(counts.values(), default=1)
