"""
@module 装饰器 —— 将一个类声明为 Canary 模块。

模块是服务的组合容器，本身也属于服务。
模块通过 services 参数声明包含的子服务/子模块，框架递归收集它们构建完整的服务树。
模块可以拥有自己的配置、生命周期钩子和依赖，与普通服务完全一致。
与 @service 的唯一区别：@module 支持 services 参数声明子节点。
"""
from __future__ import annotations

from typing import Any

from cf.core.decorators.service import is_cf_service

# 类属性标记：标识此类是否为 Canary 模块
_CF_MODULE_ATTR = "_cf_module__"
# 类属性标记：存储模块的元数据字典（name, config_cls, services）
_CF_MODULE_META = "_cf_module_meta__"


def module(
    name: str,
    *,
    config: type | None = None,
    services: list[type] | None = None,
):
    """
    将类声明为 Canary 模块。

    参数：
        name:     模块名称，全局唯一
        config:   （可选）模块自身的配置类（@config 装饰过的类）
                  如果不指定，子服务将继承父模块或更上层模块的 config_cls
        services: （可选）模块包含的子服务和子模块的类列表
                  每个元素必须是被 @service 或 @module 装饰的类

    使用示例：
        @module(
            name="AppModule",
            services=[DBService, UserService],
        )
        class AppModule:
            @on_init
            def init(self, ctx: Context):
                pass
    """
    _config = config
    _services = services or []

    def decorator(cls: type) -> type:
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not a @service "
                    f"or @module class."
                )

        meta = {
            "name": name,
            "config_cls": _config,
            "services": _services,
        }

        setattr(cls, _CF_MODULE_ATTR, True)
        setattr(cls, _CF_MODULE_META, meta)
        cls.__cf_name__ = name

        return cls

    return decorator


def is_cf_module(cls: type) -> bool:
    """判断一个类是否被 @module 装饰过。"""
    return bool(getattr(cls, _CF_MODULE_ATTR, False))


def get_module_meta(cls: type) -> dict[str, Any]:
    """获取 @module 装饰器设置的元数据字典（name, config_cls, services）。"""
    return getattr(cls, _CF_MODULE_META, {})
