"""模块装饰器 —— 将类声明为 CF 框架的模块（服务的组合容器）。

模块本身也是服务，支持配置、生命周期钩子。额外的能力是声明 services 子节点列表。
子服务/子模块通过 services 参数以类列表的形式注册到当前模块。
"""

from __future__ import annotations

from typing import Any

from canary_framework.core.decorators.service import is_cf_service

_CF_MODULE_ATTR = "_cf_module__"  # 标记: 属于 CF 模块
_CF_MODULE_META = "_cf_module_meta__"  # 存储: 元数据字典


def module(
    name: str,  # 模块名称，全局唯一
    *,
    config: type | None = None,  # 模块配置类（可选，子服务可继承）
    services: list[type] | None = None,  # 子服务和子模块类列表（可选）
):
    """将类声明为 CF 框架的模块。

    在类上设置 _cf_module__ = True 标记和 _cf_module_meta__ 元数据字典。
    框架在 _collect 阶段识别并递归处理其 services 子节点。

    Args:
        name: 模块名称，全局唯一。
        config: @config 装饰的配置类。子服务未声明 config 时继承此配置。
        services: 子服务和子模块的类列表，每个必须被 @service 或 @module 装饰。

    Raises:
        TypeError: services 列表中存在未被 @service 或 @module 装饰的类。

    Returns:
        内层装饰器函数。
    """
    _config = config
    _services = services or []

    def decorator(cls: type) -> type:
        # 校验子节点合法性
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not a @service or @module class."
                )

        meta = {"name": name, "config_cls": _config, "services": _services}
        setattr(cls, _CF_MODULE_ATTR, True)
        setattr(cls, _CF_MODULE_META, meta)
        cls.__cf_name__ = name  # type: ignore[attr-defined]
        return cls

    return decorator


def is_cf_module(cls: type) -> bool:
    """判断类是否被 @module 装饰过。"""
    return bool(getattr(cls, _CF_MODULE_ATTR, False))


def get_module_meta(cls: type) -> dict[str, Any]:
    """获取 @module 装饰器设置的元数据字典。"""
    return getattr(cls, _CF_MODULE_META, {})
