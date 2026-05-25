"""Naming utilities — PascalCase / CamelCase to snake_case conversion.

Used by the dependency injection engine to derive attribute names from
class names (e.g. ``DBService`` → ``self.db_service``).

Algorithm:
    The regular expression ``( [A-Z]+(?![a-z]) | [A-Z][a-z0-9]* )`` splits
    CamelCase into word tokens.  Pure-uppercase sequences (``DB``, ``HTTP``)
    are kept as one token; uppercase-followed-by-lowercase (``Service``,
    ``Api2``) form separate tokens.
"""

from __future__ import annotations

import re

_CAMEL_SPLIT: re.Pattern[str] = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+)")


def to_snake(name: str) -> str:
    """Convert a PascalCase / CamelCase class name to snake_case.

    Args:
        name: A class name string in PascalCase or CamelCase.

    Returns:
        The snake_case equivalent (all lowercase, words joined by ``_``).

    Examples:
        >>> to_snake("DBService")
        'db_service'
        >>> to_snake("DataSetAdminService")
        'data_set_admin_service'
        >>> to_snake("HTTPSConnection")
        'https_connection'

    Edge cases:
        * Input entirely in lowercase → returned unchanged (lowercased).
        * Input with no alphabetic characters → returned unchanged (lowercased).
        * Empty string → returns empty string.
    """
    parts = _CAMEL_SPLIT.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)
