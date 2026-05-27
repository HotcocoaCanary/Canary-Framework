"""Config decorator — marks a class as a Canary Framework config.

设计思路 (Design rationale):
    为什么需要 ``@config`` 装饰器？
    （Why do we need a @config decorator?）

    1. **显式标记**：不依赖类型注解或命名约定，框架可以明确识别配置类
       Explicit marker: the framework can identify config classes without
       relying on type hints or naming conventions.
    2. **轻量实现**：``@config`` 只是一个标记装饰器，不要求继承 pydantic
       BaseModel。任何类都可以作为配置——只需 ``@config`` 标记即可
       Lightweight: @config is a pure marker decorator. It does not
       require pydantic BaseModel inheritance. Any class works.
    3. **与 @service/@module 对称**：保持装饰器风格的 API 一致性
       Symmetry with @service/@module: consistent decorator-based API.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 标记属性 (Marker attribute)
# ---------------------------------------------------------------------------

_CONFIG_ATTR = "_cf_config__"
"""Set to ``True`` on classes decorated with ``@config``.
用于 ``is_cf_config()`` 快速判断。"""


# ---------------------------------------------------------------------------
# @config 装饰器
# ---------------------------------------------------------------------------


def config(cls: type) -> type:
    """Mark a class as a Canary Framework configuration class.

    将类标记为框架配置类。纯粹标记装饰器，不修改类行为。
    配置实例通过 ``app.config(config=...)`` 方法传入 Canary，
    之后框架自动将其设置为模块树中每个服务的 ``self.config`` 属性。

    Args:
        cls: 要标记的配置类。Any class to mark as config.

    Returns:
        同一个类（装饰器不替换）。The same class (decorator is non-wrapping).

    Example::

        @config
        class AppConfig:
            pool_size: int = 10
            timeout: int = 30
    """
    setattr(cls, _CONFIG_ATTR, True)
    return cls


# ---------------------------------------------------------------------------
# 查询工具 (Introspection helpers)
# ---------------------------------------------------------------------------


def is_cf_config(cls: type) -> bool:
    """Return ``True`` if *cls* was decorated with ``@config``.

    判断一个类是否被 ``@config`` 装饰过。

    Args:
        cls: 要检查的类。

    Returns:
        ``True`` 如果该类有 ``@config`` 标记。
    """
    return bool(getattr(cls, _CONFIG_ATTR, False))
