"""Unit tests for the parameter source markers.

参数来源标记只剩两个（``Header`` / ``Cookie``）——只有这两处是推断够不着的。
"""

from __future__ import annotations

from typing import Annotated, get_type_hints

import pytest

from canary_framework.web import Cookie, Header
from canary_framework.web.decorator.params import Param

pytestmark = pytest.mark.unit


def test_repr_round_trips_through_a_string_annotation() -> None:
    """这条是承重的，不是格式化的讲究。

    在 ``from __future__ import annotations`` 下注解全是字符串，``get_type_hints`` 会把
    ``"Annotated[str, Header(alias='x-token')]"`` 重新求值——标记对象必须能被自己的
    ``repr`` 原样重建出来，否则整条注解在求值时就炸了。
    """
    marker = Header(alias="x-token", description="调用方身份")
    assert repr(marker) == "Header(description='调用方身份', alias='x-token')"

    rebuilt = eval(repr(marker), {"Header": Header})
    assert isinstance(rebuilt, Header)
    assert (rebuilt.alias, rebuilt.description) == (marker.alias, marker.description)


def test_repr_round_trips_when_nothing_is_given() -> None:
    assert repr(Cookie()) == "Cookie()"
    assert isinstance(eval(repr(Cookie()), {"Cookie": Cookie}), Cookie)


def test_the_real_round_trip_get_type_hints_performs() -> None:
    """走一遍 get_type_hints 真正做的事：字符串注解 → 求值 → 拿回标记。"""

    def handler(token: Annotated[str, Header(alias="x-token")] = "") -> None: ...

    hints = get_type_hints(handler, include_extras=True)
    marker = hints["token"].__metadata__[0]
    assert isinstance(marker, Header)
    assert marker.alias == "x-token"


def test_each_marker_names_its_own_source() -> None:
    assert (Header().location, Cookie().location) == ("header", "cookie")
    assert isinstance(Header(), Param) and isinstance(Cookie(), Param)
