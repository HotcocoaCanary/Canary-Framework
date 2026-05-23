# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import Any

# --- 服务装饰器的标记属性名 ---
# __cf_service__ 标记类是否为 @service 装饰的服务
_CF_SERVICE_ATTR = "__cf_service__"
# __cf_service_meta__ 存储服务的元数据（名称、依赖列表、配置类）
_CF_SERVICE_META = "__cf_service_meta__"


def service(
    name: str,                      # 服务名称，全局唯一，用于依赖声明和注册表索引
    *,                              # * 之后为仅关键字参数
    config: type | None = None,     # 服务自身的配置类（@config 装饰的），None 表示无配置或继承父级
    deps: list[type] | None = None,  # 依赖的其他服务类列表，框架会自动注入这些依赖的实例
):
    # 保存参数防止闭包引用后续变化
    _config = config
    _deps = deps or []

    def decorator(cls: type) -> type:
        # 构建服务元数据字典，供后续的依赖注入、注册、排序等阶段使用
        meta = {
            "name": name,       # 服务名称
            "deps": _deps,      # 依赖的服务类列表（用于依赖注入和拓扑排序）
            "config_cls": _config,  # 配置类
        }

        # 在原始类上设置三个标记属性
        setattr(cls, _CF_SERVICE_ATTR, True)  # 标记：这是一个服务类
        setattr(cls, _CF_SERVICE_META, meta)   # 标记：存储服务的完整元数据
        cls.__cf_name__ = name                # 将名称也存储在 __cf_name__ 属性上，方便快速访问

        return cls

    return decorator


def is_cf_service(cls: type) -> bool:
    # 检查类对象上是否存在 __cf_service__ = True 标记
    # bool() 确保返回 True/False 而非 None
    return bool(getattr(cls, _CF_SERVICE_ATTR, False))


def get_service_meta(cls: type) -> dict[str, Any]:
    # 获取服务的元数据字典（包含 name, deps, config_cls）
    # 如果不是服务，getattr 返回空字典 {}
    return getattr(cls, _CF_SERVICE_META, {})
