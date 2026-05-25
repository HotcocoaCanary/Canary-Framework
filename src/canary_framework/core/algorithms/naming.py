"""Naming utilities — PascalCase / CamelCase to snake_case conversion.

设计思路 (Design rationale):
    为什么用正则而非第三方库？
    （Why regex instead of a third-party library?）

    依赖注入的核心能力不应依赖外部包。一个 5 行的正则实现足够覆盖
    所有常见 Python 类名（PascalCase），引入 ``inflection`` 等第三方库
    只会增加依赖树的复杂度。

    The regex handles three token types:
    1. ``[A-Z]+(?![a-z])`` — 纯大写序列，如 ``DB``, ``HTTP``, ``HTTPS``
       Pure-uppercase sequences (acronyms).
    2. ``[A-Z][a-z0-9]*`` — 大写开头后跟小写/数字，如 ``Service``, ``Api2``
       Capitalised words.
    3. ``[a-z0-9]+`` — 小写/数字序列，用于处理 camelCase 中的小写前缀
       Lowercase prefixes in camelCase names like ``parseXML`` → ``parse_xml``.
"""

from __future__ import annotations

import re

_CAMEL_SPLIT: re.Pattern[str] = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+)")


def to_snake(name: str) -> str:
    """Convert a PascalCase / CamelCase class name to snake_case.

    将 PascalCase / CamelCase 类名转换为 snake_case，用于依赖注入
    的属性名生成。

    Args:
        name: PascalCase 或 CamelCase 的类名字符串。
              A class name string.

    Returns:
        小写蛇形命名字符串。The snake_case equivalent.

    Edge cases:
        * 全小写输入 → 保持不变（已小写处理）
        * 无字母输入 → 保持不变
        * 空字符串 → 返回空字符串

    Examples:
        >>> to_snake("DBService")
        'db_service'
        >>> to_snake("DataSetAdminService")
        'data_set_admin_service'
        >>> to_snake("HTTPSConnection")
        'https_connection'
        >>> to_snake("parseXML")
        'parse_xml'
    """
    parts = _CAMEL_SPLIT.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)
