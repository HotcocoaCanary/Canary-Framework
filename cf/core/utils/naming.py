"""
命名工具 —— CamelCase（PascalCase）到 snake_case 的转换。

用于依赖注入：将依赖类名（如 DBService）转换为属性名（如 db_service）。

转换规则：
    - 将大写字母序列或大写字母开头的小写字母序列切分为独立的单词
    - 全部转为小写
    - 用下划线连接

    例如：
        DBService       → db_service
        UserService     → user_service
        HTTPSConnection → https_connection
        SimpleXMLParser → simple_xml_parser
"""
import re

# 用于切分 CamelCase 的正则表达式：
# ([A-Z]+(?![a-z])  —— 匹配纯大写字母序列（如 "DB"），前提是后面不跟小写字母
# [A-Z][a-z0-9]*)   —— 匹配大写字母开头后跟小写字母/数字的序列（如 "Service"）
_camel_split = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*)")


def to_snake(name: str) -> str:
    """
    将 PascalCase/CamelCase 名称转换为 snake_case。

    参数：
        name: 类名字符串（如 "DBService", "UserService"）

    返回值：
        snake_case 字符串（如 "db_service", "user_service"）

    处理逻辑：
        1. 使用正则切分单词
        2. 如果切分结果为空（纯小写输入），直接返回小写
        3. 否则将每个单词转为小写并用下划线连接
    """
    parts = _camel_split.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)
