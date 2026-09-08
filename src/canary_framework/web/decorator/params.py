"""HTTP parameter source markers — ``Header`` and ``Cookie``.

参数来源标记：只有两个，因为只有这两处是**推断够不着**的。

推断规则一句话：标量走 query（名字命中路径占位符则走 path），其余走 body。请求头和
cookie 不在签名里留下任何痕迹——``x: str`` 看不出它想读的是 ``X-Token`` 还是 ``?x=``
——所以它们必须显式说。``Query`` / ``Path`` / ``Body`` 三个标记曾经存在，但它们说的
正是推断已经给出的答案。

写法只有一种：``Annotated[str, Header()]``。默认值就用 Python 的默认值
（``Annotated[str, Header()] = "anonymous"``）——一个参数的默认值只该有一个来源。

``__repr__`` 必须可回环（round-trip）：在 ``from __future__ import annotations`` 下，
``Annotated[str, Header()]`` 会被序列化成字符串再求值，标记对象要能被
``get_type_hints`` 重建。
"""

from __future__ import annotations


class Param:
    """Base marker: where a parameter comes from, plus optional metadata.

    基类标记：来源（location）与可选元数据（description / alias）。不对外导出——
    使用者用的是 :class:`Header` 与 :class:`Cookie`。
    """

    location: str

    def __init__(self, *, description: str | None = None, alias: str | None = None) -> None:
        self.description = description
        self.alias = alias

    def __repr__(self) -> str:
        parts: list[str] = []
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        if self.alias is not None:
            parts.append(f"alias={self.alias!r}")
        return f"{type(self).__name__}({', '.join(parts)})"


class Header(Param):
    """Source: request header. ``alias`` names the wire header when it differs."""

    location = "header"


class Cookie(Param):
    """Source: request cookie. ``alias`` names the cookie when it differs."""

    location = "cookie"
