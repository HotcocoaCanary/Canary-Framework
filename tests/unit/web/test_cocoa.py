"""Unit tests for the ``@web_cocoa`` decorator."""

from __future__ import annotations

import pytest

from canary_framework.core.decorator.introspect import deps_of, is_cocoa
from canary_framework.web import web_cocoa

pytestmark = pytest.mark.unit


def test_web_cocoa_is_a_cocoa() -> None:
    @web_cocoa
    class API: ...

    assert is_cocoa(API)


def test_web_cocoa_forwards_deps() -> None:
    class Repo: ...

    @web_cocoa(deps=[Repo])
    class API: ...

    assert deps_of(API) == [Repo]
