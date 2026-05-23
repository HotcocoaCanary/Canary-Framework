# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import Any

# 从 service 模块导入类型检查工具，用于验证子服务/子模块是否合法
from cf.core.decorators.service import is_cf_service

# --- 模块装饰器的标记属性名 ---
# _cf_module__ 标记类是否为 @module 装饰的模块
_CF_MODULE_ATTR = "_cf_module__"
# _cf_module_meta__ 存储模块的元数据（名称、配置类、子服务列表）
_CF_MODULE_META = "_cf_module_meta__"


def module(
    name: str,                           # 模块名称，全局唯一，用于注册表索引
    *,                                   # * 之后为仅关键字参数，禁止位置传参
    config: type | None = None,          # 模块自身的配置类（@config 装饰的），None 表示无配置或继承父级
    services: list[type] | None = None,  # 子服务和子模块的类列表，None 等同于空列表
):
    # 保存参数防止闭包引用后续变化（Python 闭包捕获的是变量而非值）
    _config = config
    _services = services or []

    def decorator(cls: type) -> type:
        # 验证所有子服务/子模块的合法性：
        # 遍历 services 列表中的每个类，检查是否被 @service 或 @module 装饰
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                # 如果某个子服务既不是 service 也不是 module，抛出类型错误
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not a @service "
                    f"or @module class."
                )

        # 构建模块元数据字典，供后续的 _collect、注册等阶段使用
        meta = {
            "name": name,         # 模块名称
            "config_cls": _config, # 模块的配置类
            "services": _services, # 子服务和子模块列表
        }

        # 在原始类上设置三个标记属性
        setattr(cls, _CF_MODULE_ATTR, True)  # 标记：这是一个模块类
        setattr(cls, _CF_MODULE_META, meta)   # 标记：存储模块的完整元数据
        cls.__cf_name__ = name                # 将名称也存储在 __cf_name__ 属性上，方便快速访问

        return cls

    return decorator


def is_cf_module(cls: type) -> bool:
    # 检查类对象上是否存在 _cf_module__ = True 标记
    # getattr 第三个参数为默认值，属性不存在时返回 False
    return bool(getattr(cls, _CF_MODULE_ATTR, False))


def get_module_meta(cls: type) -> dict[str, Any]:
    # 获取模块的元数据字典（包含 name, config_cls, services）
    # 如果不是模块，getattr 返回空字典 {}
    return getattr(cls, _CF_MODULE_META, {})
