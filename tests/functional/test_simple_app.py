"""Functional tests for simple app."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import (
    after_init,
    before_startup,
    get,
    module,
    post,
    router,
    service,
)
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import RouterBase
from canary_framework.core.service import ServiceBase


@pytest.mark.functional
class TestSimpleApp:
    """Functional tests for a simple app."""

    @pytest.mark.asyncio
    async def test_complete_app_flow(self) -> None:
        """Test complete app flow."""

        # Define a data model
        class TodoItem(BaseModel):
            id: int | None = None
            title: str
            completed: bool = False

        # Define a service to manage todos
        @service()
        class TodoService(ServiceBase):
            def __init__(self) -> None:
                super().__init__()
                self.todos: list[TodoItem] = []
                self.next_id = 1

            def get_all(self) -> list[TodoItem]:
                return self.todos

            def get_by_id(self, todo_id: int) -> TodoItem | None:
                for todo in self.todos:
                    if todo.id == todo_id:
                        return todo
                return None

            def create(self, todo: TodoItem) -> TodoItem:
                todo.id = self.next_id
                self.next_id += 1
                self.todos.append(todo)
                return todo

        # Define a router with API endpoints
        @router()
        class TodoRouter(RouterBase):
            todo_service: TodoService

            @get("/todos")
            async def list_todos(self) -> list[dict[str, int | str | bool]]:
                return [todo.model_dump() for todo in self.todo_service.get_all()]  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

            @post("/todos", request_model=TodoItem)
            async def create_todo(self, todo: TodoItem) -> dict[str, int | str | bool]:
                created = self.todo_service.create(todo)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                return dict(created.model_dump())

        # Define the main module
        @module(services=[TodoRouter])
        class TodoApp(ModuleBase):
            @after_init
            async def setup_test_data(self) -> None:
                # Add some test data
                self.TodoRouter.todo_service.create(  # type: ignore[attr-defined]
                    TodoItem(title="Learn Canary Framework", completed=True)
                )
                self.TodoRouter.todo_service.create(  # type: ignore[attr-defined]
                    TodoItem(title="Build awesome app", completed=False)
                )

            @before_startup
            async def on_startup(self) -> None:
                pass

        # Create and configure the app
        app = TodoApp()
        await app.init()

        # Test the API endpoints
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Test list todos
            response = await client.get("/TodoRouterRouter/todos")
            assert response.status_code == 200
            todos = response.json()
            assert len(todos) == 2
            assert todos[0]["title"] == "Learn Canary Framework"
            assert todos[0]["completed"] is True

            response = await client.post(
                "/TodoRouterRouter/todos", json={"title": "New todo", "completed": False}
            )
            assert response.status_code == 200
            new_todo = response.json()
            assert new_todo["id"] == 3
            assert new_todo["title"] == "New todo"

            # Verify list now has 3 todos
            response = await client.get("/TodoRouterRouter/todos")
            assert len(response.json()) == 3

    @pytest.mark.asyncio
    async def test_openapi_docs(self) -> None:
        """Test OpenAPI docs."""

        @router()
        class MyRouter(RouterBase):
            @get("/test")
            async def test(self) -> dict[str, str]:
                return {"status": "ok"}

        @module(services=[MyRouter])
        class MyApp(ModuleBase):
            pass

        app = MyApp()
        await app.init()
        await app.startup()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Test OpenAPI JSON
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            assert "openapi" in response.json()
            assert "paths" in response.json()

            # Test Swagger UI
            response = await client.get("/docs")
            assert response.status_code == 200

            # Test ReDoc
            response = await client.get("/redoc")
            assert response.status_code == 200
