"""Test that router dependencies are properly annotated for IDE support."""

from __future__ import annotations

from typing import Any

from canary_framework.core import RouterBase
from canary_framework.decorators import get, router
from canary_framework.decorators.service import service


@service()
class KbService:
    """Test service for dependency injection."""

    def create_kb(self, request: Any) -> tuple[bool, str]:
        return True, "created"


@service()
class UserService:
    """Another test service."""

    def get_user(self, user_id: int) -> dict[str, Any]:
        return {"id": user_id, "name": "test"}


@router(prefix="/kb", deps=[KbService], tags=["kb"])
class KBRouter:
    """Router without manual attribute declaration."""

    @get("/list")
    async def list_kbs(self) -> dict[str, list[object]]:
        return {"kbs": []}


@router(prefix="/users", deps=[UserService, KbService], tags=["users"])
class UserRouter:
    """Router with multiple dependencies."""

    @get("/{user_id}")
    async def get_user(self, user_id: int) -> dict[str, Any]:
        return {"id": user_id}


class TestRouterDepsAnnotation:
    def test_single_dep_annotation(self) -> None:
        """Test that single dependency is properly annotated."""
        assert hasattr(KBRouter, "__annotations__"), "Router should have annotations"
        assert "kb_service" in KBRouter.__annotations__, "kb_service should be in annotations"
        assert KBRouter.__annotations__["kb_service"] is KbService, (
            "kb_service should be annotated as KbService"
        )

    def test_multiple_deps_annotation(self) -> None:
        """Test that multiple dependencies are properly annotated."""
        assert hasattr(UserRouter, "__annotations__"), "Router should have annotations"
        assert "user_service" in UserRouter.__annotations__, "user_service should be in annotations"
        assert "kb_service" in UserRouter.__annotations__, "kb_service should be in annotations"
        assert UserRouter.__annotations__["user_service"] is UserService
        assert UserRouter.__annotations__["kb_service"] is KbService

    def test_router_base_inheritance(self) -> None:
        """Test that router still inherits from RouterBase."""
        assert issubclass(KBRouter, RouterBase)
        assert issubclass(UserRouter, RouterBase)

    def test_preserves_existing_annotations(self) -> None:
        """Test that existing annotations are preserved."""

        @router(prefix="/test", deps=[KbService])
        class TestRouterWithExisting:
            custom_attr: str = "test"

            @get("/")
            async def handler(self) -> dict[str, bool]:
                return {"ok": True}

        assert hasattr(TestRouterWithExisting, "__annotations__")
        assert "custom_attr" in TestRouterWithExisting.__annotations__
        assert "kb_service" in TestRouterWithExisting.__annotations__
