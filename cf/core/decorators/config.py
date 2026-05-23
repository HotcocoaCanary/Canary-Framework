# 启用 PEP 563 延迟类型注解求值（Python 3.10+ 默认行为）
# 允许在类型注解中使用尚未定义的前向引用，避免循环导入问题
from __future__ import annotations

# BaseSettings：pydantic-settings 的基类，自动从环境变量和 .env 文件加载配置
# SettingsConfigDict：用于配置 BaseSettings 的行为（env_file、编码、extra 策略等）
from pydantic_settings import BaseSettings, SettingsConfigDict


def config(cls: type) -> type:
    # 1. 提取原始类中用户声明的类型注解（例如 host: str, port: int）
    #    这些注解会被 BaseSettings 用来确定环境变量名映射和类型转换
    annotations = getattr(cls, "__annotations__", {})

    # 2. 声明父类元组，只包含 BaseSettings，使动态创建的类继承其自动配置加载能力
    bases = (BaseSettings,)

    # 3. 使用 type() 动态构造一个新的 BaseSettings 子类
    #    新类的名称与原类相同，但类的实际来源换为 BaseSettings
    settings_cls = type(
        cls.__name__,    # 新类的名称（与原类保持一致）
        bases,           # 新类的父类（只有 BaseSettings）
        {
            # 将原始类的类型注解原样复制到新类中
            # BaseSettings 会读取 __annotations__ 来识别哪些字段应从环境变量加载
            "__annotations__": annotations,

            # model_config 控制 BaseSettings 的行为
            "model_config": SettingsConfigDict(
                # env_file=".env"：pydantic-settings 自动从当前目录的 .env 文件加载
                env_file=".env",
                # .env 文件使用 UTF-8 编码
                env_file_encoding="utf-8",
                # extra="ignore"：如果在 .env 或环境变量中出现了未声明的键，直接忽略而不报错
                extra="ignore",
                # env_prefix=""：无前缀匹配，配置字段名直接对应环境变量名
                env_prefix="",
            ),

            # 将原始类中用户定义的类变量复制到新类中，作为字段默认值
            # 例如 host: str = "0.0.0.0" → 新类中 host 字段默认值为 "0.0.0.0"
            # 排除名称为双下划线开头的 Python 内置属性（__module__, __qualname__ 等）
            # 以及 __annotations__ 本身（已在上面单独处理）
            **{
                k: v
                for k, v in vars(cls).items()
                if not k.startswith("__") and k != "__annotations__"
            },
        },
    )

    # 4. 覆盖 type() 自动设置的元信息，保持与原类一致，方便调试和日志输出
    settings_cls.__name__ = cls.__name__          # 类名
    settings_cls.__qualname__ = cls.__qualname__  # 完整限定名（含外覆类/函数）
    settings_cls.__module__ = cls.__module__      # 所属模块路径

    # 5. 返回动态创建的 BaseSettings 子类
    #    此后用户用此类做类型标注、构造实例时，会自动读取环境变量和 .env 文件
    return settings_cls
