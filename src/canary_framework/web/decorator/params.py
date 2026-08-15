"""HTTP parameter source markers — ``Query`` / ``Path`` / ``Header`` / ``Cookie`` / ``Body``.

参数来源标记：供 ``Annotated[T, Query(...)]`` 或 ``x: int = Query(...)`` 显式指定一个
handler 参数的来源与元数据。不加标记时，运行时按规则推断（Pydantic 模型 → body；
命中路径 ``{x}`` → path；否则 → query）。

``__repr__`` 必须可回环（round-trip）：在 ``from __future__ import annotations`` 下，
``Annotated[int, Query(default=10)]`` 会被序列化成字符串再求值，标记对象要能被
``get_type_hints`` 重建。
"""

from __future__ import annotations

from typing import Any

_UNDEFINED: Any = object()  # 哨兵：未显式提供 default


class Param:
    """Base marker: a parameter's source plus optional metadata.

    基类标记：一个参数的来源（location）与可选元数据（default / description / alias）。
    """

    location = "query"

    def __init__(
        self,
        default: Any = _UNDEFINED,
        *,
        description: str | None = None,
        alias: str | None = None,
    ) -> None:
        self.default = default
        self.description = description
        self.alias = alias

    def __repr__(self) -> str:
        parts: list[str] = []
        if self.default is not _UNDEFINED:
            parts.append(repr(self.default))
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        if self.alias is not None:
            parts.append(f"alias={self.alias!r}")
        return f"{type(self).__name__}({', '.join(parts)})"


class Query(Param):
    """Source: query string (``?a=1``)."""

    location = "query"


class Path(Param):
    """Source: path template (``/items/{item_id}``)."""

    location = "path"


class Header(Param):
    """Source: request header."""

    location = "header"


class Cookie(Param):
    """Source: request cookie."""

    location = "cookie"


class Body(Param):
    """Source: request body (parsed from JSON)."""

    location = "body"
