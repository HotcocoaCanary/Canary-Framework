"""Unit tests for mount-prefix computation — where nested web units hang."""

from __future__ import annotations

import pytest

from canary_framework import cocoa
from canary_framework.runtime.graph import build_graph
from canary_framework.runtime.mounts import join_prefix, mount_prefixes
from canary_framework.web import web_cocoa

pytestmark = pytest.mark.unit


def _mounts(*roots: type) -> dict[type, list[str]]:
    return mount_prefixes(roots, build_graph(list(roots)))


def test_prefix_nests_along_the_dependency_chain() -> None:
    @web_cocoa(prefix="/admin")
    class Admin: ...

    @web_cocoa(prefix="/api", deps=[Admin])
    class Api: ...

    assert _mounts(Api) == {Api: ["/api"], Admin: ["/api/admin"]}


def test_non_web_units_in_between_are_skipped() -> None:
    @web_cocoa(prefix="/admin")
    class Admin: ...

    @cocoa(deps=[Admin])
    class Repo: ...

    @web_cocoa(prefix="/api", deps=[Repo])
    class Api: ...

    assert _mounts(Api) == {Api: ["/api"], Admin: ["/api/admin"]}


def test_shared_unit_mounts_once_per_dependency_path() -> None:
    @web_cocoa(prefix="/c")
    class C: ...

    @web_cocoa(prefix="/b", deps=[C])
    class B: ...

    @web_cocoa(prefix="/a", deps=[B, C])
    class A: ...

    # 实例只有一个，挂载点按依赖路径各来一份
    assert _mounts(A) == {A: ["/a"], B: ["/a/b"], C: ["/a/b/c", "/a/c"]}


def test_identical_prefix_from_two_paths_is_not_duplicated() -> None:
    @web_cocoa(prefix="/c")
    class C: ...

    @web_cocoa(deps=[C])  # 无 prefix：两条路径落到同一个挂载点
    class B: ...

    @web_cocoa(prefix="/a", deps=[B, C])
    class A: ...

    assert _mounts(A) == {A: ["/a"], B: ["/a"], C: ["/a/c"]}


def test_each_root_starts_its_own_mount_path() -> None:
    @web_cocoa(prefix="/shared")
    class Shared: ...

    @web_cocoa(prefix="/one", deps=[Shared])
    class One: ...

    @web_cocoa(prefix="/two", deps=[Shared])
    class Two: ...

    assert _mounts(One, Two) == {
        One: ["/one"],
        Shared: ["/one/shared", "/two/shared"],
        Two: ["/two"],
    }


def test_root_first_order() -> None:
    @web_cocoa(prefix="/leaf")
    class Leaf: ...

    @web_cocoa(prefix="/root", deps=[Leaf])
    class Root: ...

    assert list(_mounts(Root)) == [Root, Leaf]  # 最外层在前，文档元数据取它的


def test_units_without_prefix_are_transparent() -> None:
    @web_cocoa
    class Leaf: ...

    @web_cocoa(deps=[Leaf])
    class Root: ...

    assert _mounts(Root) == {Root: [""], Leaf: [""]}


@pytest.mark.parametrize(
    ("base", "prefix", "expected"),
    [
        ("", "", ""),
        ("", "/api", "/api"),
        ("", "api", "/api"),
        ("/api", "", "/api"),
        ("/api/", "/v1/", "/api/v1"),
        ("/api", "/", "/api"),
        ("/api", "v1/users", "/api/v1/users"),
    ],
)
def test_join_prefix(base: str, prefix: str, expected: str) -> None:
    assert join_prefix(base, prefix) == expected
