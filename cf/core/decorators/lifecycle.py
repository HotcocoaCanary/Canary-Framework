"""生命周期钩子装饰器 —— @on_init / @on_start / @on_end。

用于标记服务/模块类中的方法为生命周期钩子，框架在对应阶段自动查找并调用。
钩子方法可以是 sync 或 async，框架通过 asyncio.iscoroutine 自动适配。

三个阶段:
    on_init(ctx)  — 初始化: 依赖已注入、配置已加载，接收 Context。
    on_start()    — 启动: 无参数。
    on_end()      — 停止: 无参数，按启动逆序调用。

find_hooks 查找策略:
    1. 优先查找被装饰器标记的方法（检查 __cf_on_init__ 等属性）
    2. 回退: 按方法名 on_init / on_start / on_end 直接匹配
    3. 以上均未找到 → 该阶段钩子为 None
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_CF_ON_INIT = "__cf_on_init__"  # 标记: 初始化钩子
_CF_ON_START = "__cf_on_start__"  # 标记: 启动钩子
_CF_ON_END = "__cf_on_end__"  # 标记: 停止钩子


def on_init(fn: Callable[..., Any]) -> Callable[..., Any]:
    """标记方法为 on_init 钩子。框架在其 init 阶段调用，传入 Context。"""
    setattr(fn, _CF_ON_INIT, True)
    return fn


def on_start(fn: Callable[..., Any]) -> Callable[..., Any]:
    """标记方法为 on_start 钩子。框架在其 start 阶段调用，无参数。"""
    setattr(fn, _CF_ON_START, True)
    return fn


def on_end(fn: Callable[..., Any]) -> Callable[..., Any]:
    """标记方法为 on_end 钩子。框架在其 stop 阶段按逆序调用，无参数。"""
    setattr(fn, _CF_ON_END, True)
    return fn


def find_hooks(instance: object) -> dict[str, Callable[..., Any] | None]:
    """在服务/模块实例上查找所有生命周期钩子方法。

    两步查找:
        1. 遍历 dir(instance)，通过 __cf_on_init__ 等标记属性匹配装饰的方法。
        2. 回退: 未被装饰但方法名为 on_init/on_start/on_end 的也视作钩子。

    Args:
        instance: 服务或模块的类实例。

    Returns:
        {"on_init": method | None, "on_start": method | None, "on_end": method | None}
        未找到的钩子对应值为 None。
    """
    hooks: dict[str, Callable[..., Any] | None] = {
        "on_init": None,
        "on_start": None,
        "on_end": None,
    }

    # 第一步: 检查装饰器标记
    for attr_name in dir(instance):
        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue
        if not callable(attr):
            continue

        if getattr(attr, _CF_ON_INIT, False):
            hooks["on_init"] = attr
        elif getattr(attr, _CF_ON_START, False):
            hooks["on_start"] = attr
        elif getattr(attr, _CF_ON_END, False):
            hooks["on_end"] = attr

    # 第二步: 回退 —— 未标记但恰好名称为钩子名的方法
    for key in ("on_init", "on_start", "on_end"):
        if hooks[key] is None:
            hooks[key] = getattr(instance, key, None)

    return hooks
