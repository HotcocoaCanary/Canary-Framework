"""服务装饰器 —— 将类声明为 CF 框架的服务（最小运行单元）。

服务通过 name 标识自身，通过 deps 声明依赖关系。
依赖的服务实例由框架自动注入为 snake_case 属性名。
"""

from __future__ import annotations

from typing import Any

_CF_SERVICE_ATTR = "__cf_service__"  # 标记: 属于 CF 服务
_CF_SERVICE_META = "__cf_service_meta__"  # 存储: 元数据字典


def service(
    name: str,  # 服务名称，全局唯一
    *,
    config: type | None = None,  # @config 装饰的配置类（可选）
    deps: list[type] | None = None,  # 依赖的服务类列表（可选）
):
    """将类声明为 CF 框架的服务。

    在类上设置 __cf_service__ = True 标记和 __cf_service_meta__ 元数据字典。
    框架在 _collect 阶段识别这些标记并注册该服务。

    Args:
        name: 服务名称，全局唯一，用于依赖声明和名称索引。
        config: @config 装饰的配置类，None 时从父模块继承。
        deps: 依赖的服务类列表，框架自动将其实例注入为 snake_case 属性。

    Returns:
        内层装饰器函数。
    """
    _config = config
    _deps = deps or []

    def decorator(cls: type) -> type:
        meta = {"name": name, "deps": _deps, "config_cls": _config}
        setattr(cls, _CF_SERVICE_ATTR, True)
        setattr(cls, _CF_SERVICE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


def is_cf_service(cls: type) -> bool:
    """判断类是否被 @service 装饰过。"""
    return bool(getattr(cls, _CF_SERVICE_ATTR, False))


def get_service_meta(cls: type) -> dict[str, Any]:
    """获取 @service 装饰器设置的元数据字典。"""
    return getattr(cls, _CF_SERVICE_META, {})
