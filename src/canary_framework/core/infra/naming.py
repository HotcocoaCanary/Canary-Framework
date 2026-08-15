"""Naming utilities — camelCase to snake_case.

命名工具：把类名转换成依赖注入的属性名。
"""

import re

_CAMEL_SPLIT = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+)")


def to_snake(name: str) -> str:
    """``UserService`` -> ``user_service`` — the injected attribute name.

    按 snake_case 生成注入属性名（``UserService`` → ``user_service``）。
    """
    parts = _CAMEL_SPLIT.findall(name)
    return "_".join(p.lower() for p in parts) if parts else name.lower()
