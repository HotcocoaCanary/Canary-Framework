"""
@service 装饰器 —— 将一个普通类声明为 Canary 框架的服务。

服务是框架的最小运行单元，声明生命周期钩子后由框架统一管理其初始化、启动和停止。
服务之间可以通过 deps 参数声明依赖关系，框架会在启动时自动注入依赖实例。
"""
from __future__ import annotations

from typing import Any

# 类属性标记：标识此类是否为 Canary 服务
_CF_SERVICE_ATTR = "__cf_service__"
# 类属性标记：存储服务的元数据字典（name, deps, config_cls）
_CF_SERVICE_META = "__cf_service_meta__"


def service(
    name: str,
    *,
    config: type | None = None,
    deps: list[type] | None = None,
):
    """
    将类声明为 Canary 服务。

    参数：
        name:   服务名称，全局唯一，用于依赖声明和注册表索引
        config: （可选）由 @config 装饰的配置类
                如果不指定且存在父模块，则继承父模块的 config_cls
        deps:   （可选）该服务依赖的其他服务类列表
                框架会在初始化时自动将依赖服务的实例注入到当前实例的属性上
                （属性名为依赖类名的 snake_case 形式，如 self.db_service）

    使用示例：
        @service(
            name="UserService",
            config=UserConfig,
            deps=[DBService],
        )
        class UserService:
            @on_init
            def init(self, ctx: Context):
                self.db_service.connect(ctx.config.db_url)
    """
    _config = config
    _deps = deps or []

    def decorator(cls: type) -> type:
        meta = {
            "name": name,
            "deps": _deps,
            "config_cls": _config,
        }

        setattr(cls, _CF_SERVICE_ATTR, True)
        setattr(cls, _CF_SERVICE_META, meta)
        cls.__cf_name__ = name

        return cls

    return decorator


def is_cf_service(cls: type) -> bool:
    """判断一个类是否被 @service 装饰过。"""
    return bool(getattr(cls, _CF_SERVICE_ATTR, False))


def get_service_meta(cls: type) -> dict[str, Any]:
    """获取 @service 装饰器设置的元数据字典（name, deps, config_cls）。"""
    return getattr(cls, _CF_SERVICE_META, {})
