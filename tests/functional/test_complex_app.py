"""Functional tests for complex app."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import get, module, post, router, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase
from canary_framework.core.service import ServiceBase


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
        class UserService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.users: list[User] = []

            def create(self, user: User) -> User:
                user.id = len(self.users) + 1
                self.users.append(user)
                return user

            def get_all(self) -> list[User]:
                return self.users

        @router()
        class UserRouter(RouterBase):
            user_service: UserService

            @get("/users")
            async def list_users(self) -> list[User]:
                return self.user_service.get_all()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]

            @post("/users", request_model=User)
            async def create_user(self, user: User) -> User:
                return self.user_service.create(user)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]

        @module(services=[UserService, UserRouter])
        class UserModule(ModuleBase):
            pass

        # Product module
        class Product(BaseModel):
            id: int | None = None
            name: str
            price: float

        @service()
        class ProductService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.products: list[Product] = []

            def create(self, product: Product) -> Product:
                product.id = len(self.products) + 1
                self.products.append(product)
                return product

            def get_all(self) -> list[Product]:
                return self.products

        @router()
        class ProductRouter(RouterBase):
            product_service: ProductService

            @get("/products")
            async def list_products(self) -> list[Product]:
                return self.product_service.get_all()

            @post("/products", request_model=Product)
            async def create_product(self, product: Product) -> Product:
                return self.product_service.create(product)

        @module(services=[ProductService, ProductRouter])
        class ProductModule(ModuleBase):
            pass

        # Main app module
        @module(services=[UserModule, ProductModule])
        class MainApp(ModuleBase):
            pass

        # Create and configure app
        app = MainApp()
        await app.configure()

        # Test both modules
        async with AsyncClient(
            transport=ASGITransport(app=app),
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
