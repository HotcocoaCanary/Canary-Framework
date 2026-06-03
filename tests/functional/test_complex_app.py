"""Functional tests for complex app."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import get, module, post, router, service


@pytest.mark.functional
class TestComplexApp:
    """Functional tests for a complex app with multiple modules."""

    @pytest.mark.asyncio
    async def test_multi_module_app(self) -> None:
        """Test multi-module app."""

        # User module
        class User(BaseModel):
            id: int | None = None
            name: str
            email: str

        @service()
        class UserService:
            def __init__(self) -> None:
                self.users: list[User] = []

            def create(self, user: User) -> User:
                user.id = len(self.users) + 1
                self.users.append(user)
                return user

            def get_all(self) -> list[User]:
                return self.users

        @router(deps=[UserService])
        class UserRouter:
            @get("/users")
            async def list_users(self) -> list[User]:
                return self.user_service.get_all()  # type: ignore[attr-defined, no-any-return]

            @post("/users", request_model=User)
            async def create_user(self, user: User) -> User:
                return self.user_service.create(user)  # type: ignore[attr-defined, no-any-return]

        @module(services=[UserService, UserRouter])
        class UserModule:
            pass

        # Product module
        class Product(BaseModel):
            id: int | None = None
            name: str
            price: float

        @service()
        class ProductService:
            def __init__(self) -> None:
                self.products: list[Product] = []

            def create(self, product: Product) -> Product:
                product.id = len(self.products) + 1
                self.products.append(product)
                return product

            def get_all(self) -> list[Product]:
                return self.products

        @router(deps=[ProductService])
        class ProductRouter:
            @get("/products")
            async def list_products(self) -> list[Product]:
                return self.product_service.get_all()  # type: ignore[attr-defined, no-any-return]

            @post("/products", request_model=Product)
            async def create_product(self, product: Product) -> Product:
                return self.product_service.create(product)  # type: ignore[attr-defined, no-any-return]

        @module(services=[ProductService, ProductRouter])
        class ProductModule:
            pass

        # Main app module
        @module(services=[UserModule, ProductModule])
        class MainApp:
            pass

        # Create and configure app
        app = MainApp()
        await app.configure()  # type: ignore[attr-defined]

        # Test both modules
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            # Test user module
            response = await client.post(
                "/UserModuleModule/UserRouterRouter/users",
                json={"name": "Alice", "email": "alice@example.com"},
            )
            assert response.status_code == 200

            response = await client.get("/UserModuleModule/UserRouterRouter/users")
            assert len(response.json()) == 1

            # Test product module
            response = await client.post(
                "/ProductModuleModule/ProductRouterRouter/products",
                json={"name": "Laptop", "price": 999.99},
            )
            assert response.status_code == 200

            response = await client.get("/ProductModuleModule/ProductRouterRouter/products")
            assert len(response.json()) == 1
