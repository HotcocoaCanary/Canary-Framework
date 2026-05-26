"""Tests for :mod:`canary_framework.core.decorators.module`.

Covers:
    - @module validation: TypeError when child is not a framework class
    - get_module_meta fallback for non-module classes
"""

from __future__ import annotations

import pytest

from canary_framework.common._types import ModuleMeta
from canary_framework.core.decorators.module import (
    get_module_meta,
    is_cf_module,
    module,
)
from canary_framework.core.decorators.service import is_cf_service, service


@pytest.mark.unit
class TestModuleValidation:
    """Verify @module validates child services at decoration time."""

    def test_non_framework_child_raises_typeerror(self) -> None:
        class NotDecorated:
            pass

        with pytest.raises(
            TypeError,
            match="not decorated with @service or @module",
        ):
            @module("bad", services=[NotDecorated])  # type: ignore[arg-type]
            class BadModule:
                pass

    def test_module_is_also_service(self) -> None:
        @module("test-mod", services=[])
        class M:
            pass

        assert is_cf_module(M) is True
        assert is_cf_service(M) is True


@pytest.mark.unit
class TestGetModuleMeta:
    """Verify get_module_meta() introspection."""

    def test_returns_module_meta_for_module(self) -> None:
        @service("child")
        class Child:
            pass

        @module("parent", services=[Child])
        class Parent:
            pass

        meta = get_module_meta(Parent)
        assert isinstance(meta, ModuleMeta)
        assert meta.name == "parent"
        assert meta.services == [Child]

    def test_returns_default_for_non_module(self) -> None:
        class Plain:
            pass

        meta = get_module_meta(Plain)
        assert isinstance(meta, ModuleMeta)
        assert meta.name == ""

    def test_returns_default_for_plain_service(self) -> None:
        @service("svc")
        class Svc:
            pass

        meta = get_module_meta(Svc)
        assert isinstance(meta, ModuleMeta)
        assert meta.name == ""
