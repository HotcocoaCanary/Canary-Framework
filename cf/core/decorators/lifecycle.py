# 启用 PEP 563 延迟类型注解求值，提供对 Any、Callable 等类型的使用
from __future__ import annotations

from typing import Any, Callable

# --- 钩子标记属性名常量 ---
# 框架通过这三个属性来识别方法是否被对应的生命周期装饰器标记
# 属性名以 __cf_ 开头避免与用户定义的属性冲突
_CF_ON_INIT  = "__cf_on_init__"   # 标记方法为初始化钩子（on_init 阶段调用）
_CF_ON_START = "__cf_on_start__"  # 标记方法为启动钩子（on_start 阶段调用）
_CF_ON_END   = "__cf_on_end__"    # 标记方法为停止钩子（on_end 阶段调用）


def on_init(fn: Callable[..., Any]) -> Callable[..., Any]:
    # 使用 setattr 在函数/方法对象上设置 __cf_on_init__ = True
    # 这是一种"打标"模式：不修改函数行为，只添加一个可被框架读取的标识属性
    # 框架在 find_hooks() 中通过检查此属性来识别标记的钩子
    setattr(fn, _CF_ON_INIT, True)
    # 原样返回函数，装饰器对函数的调用行为不做任何修改
    return fn


def on_start(fn: Callable[..., Any]) -> Callable[..., Any]:
    # 在方法上标记 __cf_on_start__ = True，表示该方法应在 start() 阶段被调用
    setattr(fn, _CF_ON_START, True)
    # 返回原函数不进行包装
    return fn


def on_end(fn: Callable[..., Any]) -> Callable[..., Any]:
    # 在方法上标记 __cf_on_end__ = True，表示该方法应在 stop() 阶段被调用
    # stop 阶段按启动顺序的逆序调用（拓扑排序的逆序），先启动的后停止
    setattr(fn, _CF_ON_END, True)
    # 返回原函数不进行包装
    return fn


def find_hooks(instance: object) -> dict[str, Callable[..., Any] | None]:
    # 初始化钩子结果字典，所有三个阶段默认都为 None（表示该阶段无钩子）
    hooks: dict[str, Callable[..., Any] | None] = {
        "on_init": None,
        "on_start": None,
        "on_end": None,
    }

    # 遍历实例对象的所有属性（包括继承的方法和属性）
    # dir() 返回对象的所有属性名列表，按字母排序
    for attr_name in dir(instance):
        try:
            # 获取属性值（即实际的方法或属性对象）
            attr = getattr(instance, attr_name)
        except Exception:
            # 某些属性可能在访问时抛出异常（如惰性属性、描述符等），遇到则跳过
            continue
        if not callable(attr):
            # 只关心可调用对象（方法），跳过普通属性
            continue

        # 按优先级检查装饰器标记（只取第一个匹配的标记，因为一个方法不会被多个生命周期装饰）
        if getattr(attr, _CF_ON_INIT, False):
            hooks["on_init"] = attr   # 找到了 on_init 钩子方法
        elif getattr(attr, _CF_ON_START, False):
            hooks["on_start"] = attr  # 找到了 on_start 钩子方法
        elif getattr(attr, _CF_ON_END, False):
            hooks["on_end"] = attr    # 找到了 on_end 钩子方法

    # 回退机制：对装饰器未标记但名称匹配的生命周期钩子，直接尝试按名称获取
    # 例如：类中定义了 def on_init(self, ctx) 方法但忘记加 @on_init 装饰器，也能被识别
    # 但装饰器标记的优先级更高，已在上面步骤中被设置，此处不会覆盖
    for key in ("on_init", "on_start", "on_end"):
        if hooks[key] is None:
            hooks[key] = getattr(instance, key, None)

    return hooks
