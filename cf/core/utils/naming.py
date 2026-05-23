"""命名工具 —— PascalCase / CamelCase 与 snake_case 的转换。

用于依赖注入时，将依赖类名（如 DBService）转换为属性名（如 db_service）。
"""
import re

# 正则: 切分 CamelCase 为单词列表
# [A-Z]+(?![a-z]) — 纯大写序列（如 DB、HTTP）
# [A-Z][a-z0-9]* — 大写开头后跟小写/数字（如 Service、Api2）
_camel_split = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*)")


def to_snake(name: str) -> str:
    """将 PascalCase / CamelCase 名称转换为 snake_case。

    Examples:
        >>> to_snake("DBService")
        "db_service"
        >>> to_snake("DataSetAdminService")
        "data_set_admin_service"
        >>> to_snake("HTTPSConnection")
        "https_connection"

    Args:
        name: 类名字符串（PascalCase）。

    Returns:
        snake_case 形式的小写字符串。
    """
    parts = _camel_split.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)
