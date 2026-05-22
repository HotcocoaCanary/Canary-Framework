"""
@config 装饰器 —— 将普通类转换为基于 pydantic-settings 的配置类。

被 @config 装饰的类可以声明类型注解的属性，这些属性会自动从环境变量
和 .env 文件中读取。所有服务的配置文件路径统一由 Canary.init(config_file_path=".env") 传入。

使用示例：
    @config
    class AppConfig:
        host: str = "0.0.0.0"       # 默认值，可被环境变量 HOST 或 .env 中 HOST 覆盖
        port: int = 8000
        log_level: str = "INFO"

支持两种写法：
    @config              # 无括号直接使用
    class MyConfig: ...

    @config()            # 有空括号也支持
    class MyConfig: ...

工作原理：
    @config 装饰器动态创建一个 pydantic_settings.BaseSettings 的子类，
    将原始类的类型注解和类变量复制到该子类中。
    框架在 _init 阶段通过 _instantiate_config() 实例化该配置类并注入到 service context。
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def config(cls: type) -> type:
    """
    将普通类转换为 pydantic_settings.BaseSettings 子类。

    处理步骤：
        1. 提取原始类的类型注解（如 host: str, port: int）
        2. 提取原始类的类变量（如 host = "0.0.0.0"），排除 dunder 属性和 __annotations__
        3. 使用 type() 动态创建一个新的 BaseSettings 子类
        4. 设置 model_config：指定 env_file 为 None（实际加载路径在 _instantiate_config 中指定），
           extra="ignore" 表示忽略未声明的环境变量
        5. 保持原始类的 name/qualname/module 以方便调试

    参数：
        cls: 被 @config 装饰的原始类（包含类型注解和默认值的普通类）

    返回值：
        新的 BaseSettings 子类（具有自动 env 加载能力）
    """
    # 提取原始类的类型注解（Python 的类型提示）
    annotations = getattr(cls, "__annotations__", {})
    # BaseSettings 作为父类
    bases = (BaseSettings,)

    # 动态创建新类，名称与原类相同但继承自 BaseSettings
    settings_cls = type(
        cls.__name__,
        bases,
        {
            # 在 BaseSettings 子类中，类型注解会被用来自动解析环境变量
            "__annotations__": annotations,
            # pydantic-settings 的模型配置
            "model_config": SettingsConfigDict(
                env_file=None,  # 实际 env_file 路径在实例化时通过 _env_file 指定
                env_file_encoding="utf-8",
                extra="ignore",  # 忽略环境变量中未在类中声明的字段
                env_prefix="",  # 无前缀，直接使用变量名匹配
            ),
            # 将原始类的类变量复制到新类中（作为字段默认值）
            # 排除双下划线属性（如 __module__, __qualname__）和 __annotations__ 本身
            **{
                k: v
                for k, v in vars(cls).items()
                if not k.startswith("__") and k != "__annotations__"
            },
        },
    )
    # 保持原始类的元信息以便调试和日志
    settings_cls.__name__ = cls.__name__
    settings_cls.__qualname__ = cls.__qualname__
    settings_cls.__module__ = cls.__module__
    return settings_cls
