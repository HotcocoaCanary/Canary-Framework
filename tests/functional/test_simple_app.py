"""Functional tests for the 0.6 public application API."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from starlette.testclient import TestClient

import canary_framework as cf
from canary_framework.core import ModuleBase, RouterBase, ServiceBase

pytestmark = pytest.mark.functional


def test_public_surface_contains_only_new_routing_and_lifecycle_names() -> None:
    for name in ("service", "router", "module", "get", "post", "put", "delete", "patch"):
        assert name in cf.__all__
        assert hasattr(cf, name)
    for removed in ("Router", "LifecycleHook", "before_startup", "before_shutdown"):
        assert removed not in cf.__all__
        assert not hasattr(cf, removed)


async def test_one_router_is_a_complete_application() -> None:
    @cf.router(prefix="/health")
    class HealthRouter(RouterBase):
        @cf.get("")
        async def health(self) -> dict[str, str]:
            return {"status": "ok"}

    app = HealthRouter()
    await app.init()
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/openapi.json").status_code == 200


async def test_complete_app_flow() -> None:
    class TodoItem(BaseModel):
        id: int | None = None
        title: str
        completed: bool = False

    @cf.service()
    class TodoService(ServiceBase):
        def __init__(self) -> None:
            super().__init__()
            self.todos = [
                TodoItem(id=1, title="Learn Canary", completed=True),
                TodoItem(id=2, title="Build an app"),
            ]

        def create(self, todo: TodoItem) -> TodoItem:
            todo.id = len(self.todos) + 1
            self.todos.append(todo)
            return todo

    @cf.router()
    class TodoRouter(RouterBase):
        todo_service: TodoService

        @cf.get("/todos")
        async def list_todos(self) -> list[TodoItem]:
            return self.todo_service.todos

        @cf.post("/todos", request_model=TodoItem)
        async def create_todo(self, todo: TodoItem) -> TodoItem:
            return self.todo_service.create(todo)

    @cf.module(children=(TodoRouter,))
    class TodoApp(ModuleBase):
        pass

    app = TodoApp()
    await app.init()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/todos")
        assert [item["title"] for item in response.json()] == ["Learn Canary", "Build an app"]
        response = await client.post("/todos", json={"title": "New todo"})
        assert response.json()["id"] == 3
        assert len((await client.get("/todos")).json()) == 3


async def test_openapi_docs() -> None:
    @cf.router()
    class MyRouter(RouterBase):
        @cf.get("/test")
        async def test(self) -> dict[str, str]:
            return {"status": "ok"}

    @cf.module(children=(MyRouter,))
    class MyApp(ModuleBase):
        pass

    app = MyApp()
    await app.init()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        schema = await client.get("/openapi.json")
        assert schema.status_code == 200
        assert "paths" in schema.json()
        assert (await client.get("/docs")).status_code == 200
        assert (await client.get("/redoc")).status_code == 200
