"""Functional tests for nested modules and transitive service discovery."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import get, module, post, router, service
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.functional


async def test_multi_module_app_discovers_router_services_transitively() -> None:
    class User(BaseModel):
        id: int | None = None
        name: str

    @service()
    class UserService(ServiceBase):
        def __init__(self) -> None:
            super().__init__()
            self.users: list[User] = []

        def create(self, user: User) -> User:
            user.id = len(self.users) + 1
            self.users.append(user)
            return user

    @router()
    class UserRouter(RouterBase):
        users: UserService

        @get("/users")
        async def list_users(self) -> list[User]:
            return self.users.users

        @post("/users", request_model=User)
        async def create_user(self, user: User) -> User:
            return self.users.create(user)

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

    @router()
    class ProductRouter(RouterBase):
        products: ProductService

        @get("/products")
        async def list_products(self) -> list[Product]:
            return self.products.products

        @post("/products", request_model=Product)
        async def create_product(self, product: Product) -> Product:
            return self.products.create(product)

    @module(children=(UserRouter,))
    class UserModule(ModuleBase):
        pass

    @module(children=(ProductRouter,))
    class ProductModule(ModuleBase):
        pass

    @module(children=(UserModule, ProductModule))
    class MainApp(ModuleBase):
        pass

    app = MainApp()
    await app.init()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/users", json={"name": "Alice"})).status_code == 200
        assert len((await client.get("/users")).json()) == 1
        assert (
            await client.post("/products", json={"name": "Laptop", "price": 999.99})
        ).status_code == 200
        assert len((await client.get("/products")).json()) == 1
