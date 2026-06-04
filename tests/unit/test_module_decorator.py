"""Unit tests for decorators.module module."""

import pytest

from canary_framework.common import get_module_meta, is_cf_module, is_cf_service
from canary_framework.core.module import ModuleBase
from canary_framework.core.service import ServiceBase
from canary_framework.decorators.module import module
from canary_framework.decorators.service import service


@pytest.mark.unit
class TestModuleDecorator:
    """Tests for @module decorator."""

    def test_module_decorator_marks_class(self) -> None:
        """Test @module marks class as module."""

        @module()
        class MyModule(ModuleBase):
            pass

        assert is_cf_module(MyModule)
        assert is_cf_service(MyModule)  # Modules are also services

    def test_module_decorator_inherits_module_base(self) -> None:
        """Test @module makes class inherit from ModuleBase."""

        @module()
        class MyModule(ModuleBase):
            pass

        assert issubclass(MyModule, ModuleBase)

    def test_module_decorator_sets_meta(self) -> None:
        """Test @module sets metadata."""

        @module()
        class MyModule(ModuleBase):
            pass

        meta = get_module_meta(MyModule)
        assert meta.name == "MyModuleModule"
        assert meta.services == []

    def test_module_decorator_with_services(self) -> None:
        """Test @module with services."""

        @service()
        class MyService(ServiceBase):
            pass

        @module(services=[MyService])
        class MyModule(ModuleBase):
            pass

        meta = get_module_meta(MyModule)
        assert meta.services == [MyService]

    def test_module_decorator_with_undecorated_service_raises(self) -> None:
        """Test @module with undecorated service raises TypeError."""

        class UndecoratedService:
            pass

        with pytest.raises(TypeError):

            @module(services=[UndecoratedService])
            class MyModule(ModuleBase):
                pass
