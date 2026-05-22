"""
生命周期钩子装饰器 —— @on_init, @on_start, @on_end。

这些装饰器用于标记服务/模块类中的方法为生命周期钩子，框架在对应的生命周期阶段
会自动查找并调用这些钩子方法。

生命周期三个阶段：
    1. on_init(ctx)  —— 初始化阶段，接收 Context 上下文对象作为参数
                       此时依赖已注入、配置已加载，适合做日志配置、连接池初始化
    2. on_start()    —— 启动阶段，无参数
                       适合做连接建立、注册到服务发现等操作
    3. on_end()      —— 停止阶段，无参数
                       适合做资源释放、优雅关闭等操作

钩子查找策略（find_hooks）：
    1. 优先查找被 @on_init / @on_start / @on_end 装饰器标记的方法
    2. 如果没有找到被标记的方法，回退到以钩子名称命名的普通方法（on_init/on_start/on_end）
    3. 如果都没有，该阶段的钩子为 None，框架将跳过该阶段

钩子方法可以是同步函数或异步协程，框架会自动判断并处理（通过 asyncio.iscoroutine）。
"""
from __future__ import annotations

from typing import Any, Callable

# 钩子方法上的标记属性名
_CF_ON_INIT  = "__cf_on_init__"   # 标记该方法为初始化钩子
_CF_ON_START = "__cf_on_start__"  # 标记该方法为启动钩子
_CF_ON_END   = "__cf_on_end__"    # 标记该方法为停止钩子


def on_init(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    标记方法为初始化钩子。

    该方法在框架的 init() 阶段被调用，接收上下文对象作为参数：
        def my_init(self, ctx: Context):  # 或 async def

    典型用途：
        - 配置日志等级（ctx.config.log_level）
        - 初始化数据库连接池
        - 读取配置中的启动参数

    参数：
        fn: 被装饰的服务/模块方法

    返回值：
        装饰后的方法（功能不变，只是添加了标记属性）
    """
    setattr(fn, _CF_ON_INIT, True)
    return fn


def on_start(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    标记方法为启动钩子。

    该方法在框架的 start() 阶段被调用，不接收任何额外参数（除了 self）。

    典型用途：
        - 建立数据库/外部服务连接
        - 注册到服务发现
        - 启动后台任务/定时器

    参数：
        fn: 被装饰的服务/模块方法

    返回值：
        装饰后的方法（添加了标记属性）
    """
    setattr(fn, _CF_ON_START, True)
    return fn


def on_end(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    标记方法为停止钩子。

    该方法在框架的 stop() 阶段被调用，不接收任何额外参数（除了 self）。
    停止顺序为拓扑序的逆序：先启动的后停止，后启动的先停止。

    典型用途：
        - 关闭数据库连接
        - 释放外部服务资源
        - 取消后台任务

    参数：
        fn: 被装饰的服务/模块方法

    返回值：
        装饰后的方法（添加了标记属性）
    """
    setattr(fn, _CF_ON_END, True)
    return fn


def find_hooks(instance: object) -> dict[str, Callable[..., Any] | None]:
    """
    在服务/模块实例上查找所有生命周期钩子方法。

    查找策略：
        1. 遍历实例的所有属性和方法，检查是否被对应的钩子装饰器标记
        2. 对于未被装饰器标记的钩子，回退到以钩子名称命明的普通方法
           （如实例有一个名为 on_init 的方法但未用 @on_init 装饰，也会被视为钩子）

    参数：
        instance: 服务或模块的类实例

    返回值：
        字典 {"on_init": method_or_None, "on_start": method_or_None, "on_end": method_or_None}
        未找到的钩子对应的值为 None
    """
    # 初始化返回值，所有钩子默认为 None
    hooks: dict[str, Callable[..., Any] | None] = {
        "on_init": None,
        "on_start": None,
        "on_end": None,
    }

    # 遍历实例的所有属性和方法
    for attr_name in dir(instance):
        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue  # 某些属性可能在访问时抛异常，跳过
        if not callable(attr):
            continue  # 只关心可调用的方法

        # 检查方法上是否有钩子标记
        if getattr(attr, _CF_ON_INIT, False):
            hooks["on_init"] = attr
        elif getattr(attr, _CF_ON_START, False):
            hooks["on_start"] = attr
        elif getattr(attr, _CF_ON_END, False):
            hooks["on_end"] = attr

    # 回退：对于没有用装饰器标记的钩子，尝试用名称直接查找
    # 例如：如果类有一个 def on_init(self, ctx) 方法但未加 @on_init 装饰器，仍能被识别
    for key in ("on_init", "on_start", "on_end"):
        if hooks[key] is None:
            hooks[key] = getattr(instance, key, None)

    return hooks
