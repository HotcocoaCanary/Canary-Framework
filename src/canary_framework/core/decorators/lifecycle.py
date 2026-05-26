"""Lifecycle hook decorators and typed hook registry.

设计思路 (Design rationale):
    为什么使用显式装饰器而非方法名约定？
    （Why explicit decorators instead of method-name convention?）

    1. **可发现性**：装饰器让钩子意图一目了然，IDE 可以高亮和跳转
       Discoverability: decorators make hook intent obvious; IDEs can highlight.
    2. **防误触**：用户可能恰好定义了名为 ``on_init`` 的方法但并非钩子，
       旧版的 fallback 机制会导致框架误调用
       Safety: a method named ``on_init`` may not be intended as a hook.
    3. **可扩展**：未来新增钩子类型不会与现有方法名冲突
       Extensibility: adding new hook types won't collide with existing names.

标记机制 (Marker mechanism):
    每个装饰器在方法上设置一个私有属性（如 ``__cf_on_init__``）作为标记。
    ``find_hooks`` 通过 ``dir()`` 遍历实例的所有属性，检查这些标记。
    这种方案避免了维护全局注册表，也不依赖方法名。
"""

from __future__ import annotations

from collections.abc import Callable

from canary_framework.common.enums import LifecycleHook

# ---------------------------------------------------------------------------
# 标记属性映射
# Marker attribute mapping — each LifecycleHook maps to a private dunder attr
# ---------------------------------------------------------------------------

_MARKER_MAP: dict[LifecycleHook, str] = {
    LifecycleHook.INIT: "__cf_on_init__",
    LifecycleHook.START: "__cf_on_start__",
    LifecycleHook.END: "__cf_on_end__",
}


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def on_init[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``on_init`` lifecycle hook.

    标记方法为初始化钩子。框架在 init 阶段调用，此时依赖（含 config）已注入。

    Args:
        fn: 要标记的方法。A method to mark.

    Returns:
        同一个方法（装饰器不替换函数）。The same method (decorator is non-wrapping).

    Example::

        @service(name="db", config=DBConfig, deps=[CacheService])
        class DBService:
            db_config: DBConfig
            cache_service: CacheService

            @on_init
            def init(self) -> None:
                self.pool = create_pool(self.db_config.dsn)
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.INIT], True)
    return fn


def on_start[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``on_start`` lifecycle hook.

    标记方法为启动钩子。按拓扑序在 ``Canary.start()`` 中调用，无参数。
    适合启动连接池、注册信号处理器等操作。

    Args:
        fn: 要标记的方法。A method to mark.

    Returns:
        同一个方法。The same method.

    Example::

        @on_start
        def start(self) -> None:
            self.server.listen()
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.START], True)
    return fn


def on_end[FnT: Callable[..., object]](fn: FnT) -> FnT:
    """Mark a method as the ``on_end`` lifecycle hook.

    标记方法为停止钩子。按逆拓扑序在 ``Canary.stop()`` 中调用，无参数。
    依赖方先停止，被依赖方后停止。适合关闭连接、刷新缓冲区等清理操作。

    Args:
        fn: 要标记的方法。A method to mark.

    Returns:
        同一个方法。The same method.

    Example::

        @on_end
        def stop(self) -> None:
            self.pool.close()
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.END], True)
    return fn


# ---------------------------------------------------------------------------
# Hook discovery
# ---------------------------------------------------------------------------

HookDict = dict[LifecycleHook, Callable[..., object] | None]
"""Return type of :func:`find_hooks` — maps each lifecycle hook to the
bound method, or ``None`` if not defined.

返回值中所有三个钩子键都存在，未定义的钩子对应值为 ``None``。
All three hook keys are always present; missing hooks map to ``None``.
"""


def find_hooks(instance: object) -> HookDict:
    """Discover lifecycle hooks on a service or module instance.

    通过 ``dir()`` 遍历实例的所有属性，检查每个可调用对象是否带有
    装饰器设置的标记属性（``__cf_on_init__`` 等）。

    设计要点 (Key design points):
        - **只识别装饰过的**：不按方法名匹配，防止隐式行为
          Only decorated methods are recognised — no name-based fallback.
        - **只取第一个**：某个钩子的多个方法中只取先发现的
          First match wins when multiple methods share a marker.
        - **异常安全**：跳过无法读取的属性（如 ``__getattr__`` 抛异常）
          Exception-safe: skips attributes that throw on access.

    Args:
        instance: 已构造的服务或模块实例。
                  A constructed service or module instance.

    Returns:
        每个 LifecycleHook 到绑定方法的映射，未定义的为 ``None``。
        A :class:`HookDict` mapping each hook to the bound method or ``None``.

    性能 (Performance):
        每个实例最多扫描一次；结果会缓存在 ``ServiceEntry._hooks`` 中。
        Scanned at most once per instance; result cached on ``ServiceEntry._hooks``.
    """
    hooks: HookDict = {
        LifecycleHook.INIT: None,
        LifecycleHook.START: None,
        LifecycleHook.END: None,
    }

    for attr_name in dir(instance):
        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue  # 跳过无法访问的属性（如动态 property 报错）
        if not callable(attr):
            continue

        # 检查每个标记，找到第一个匹配的钩子类型
        # Check each marker; assign to the first matching hook
        for hook, marker in _MARKER_MAP.items():
            if getattr(attr, marker, False) and hooks[hook] is None:
                hooks[hook] = attr
                break

        # 短路：所有钩子都已找到，无需继续遍历
        # Short-circuit: all hooks found, no need to continue scanning
        if all(v is not None for v in hooks.values()):
            break

    return hooks
