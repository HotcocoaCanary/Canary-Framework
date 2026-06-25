"""Functional tests for simple app."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from canary_framework import (
    Canary,
    module,
    service,
)
from canary_framework.core.web.router import Router


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
        class TodoService:
            def __init__(self) -> None:
                super().__init__()
                self.todos: list[TodoItem] = []
                self.next_id = 1
                self.create(TodoItem(title="Learn Canary", completed=True))
                self.create(TodoItem(title="Build an app", completed=False))

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
        @service()
        class TodoRouter:
            router = Router()
            todo_service: TodoService

            @router.get("/todos")
            async def list_todos(self) -> list[dict[str, int | str | bool]]:
                return [todo.model_dump() for todo in self.todo_service.get_all()]  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

            @router.post("/todos", request_model=TodoItem)
            async def create_todo(self, todo: TodoItem) -> dict[str, int | str | bool]:
                created = self.todo_service.create(todo)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                return dict(created.model_dump())

        # Define the main module
        @module(services=[TodoRouter])
        class TodoApp:
            async def setup_test_data(self) -> None:
                # Add some test data
                self.TodoRouter.todo_service.create(  # type: ignore[attr-defined]
                    TodoItem(title="Learn Canary", completed=True)
                )
                self.TodoRouter.todo_service.create(  # type: ignore[attr-defined]
                    TodoItem(title="Build awesome app", completed=False)
                )

            async def startup(self) -> None:
                await self.setup_test_data()

        # Create and configure the app
        app = Canary(TodoApp())

        # Test the API endpoints
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Test list todos
            response = await client.get("/TodoRouter/todos")
            assert response.status_code == 200
            todos = response.json()
            assert len(todos) == 2
            assert todos[0]["title"] == "Learn Canary"
            assert todos[0]["completed"] is True

            response = await client.post(
                "/TodoRouter/todos", json={"title": "New todo", "completed": False}
            )
            assert response.status_code == 200
            new_todo = response.json()
            assert new_todo["id"] == 3
            assert new_todo["title"] == "New todo"

            # Verify list now has 3 todos
            response = await client.get("/TodoRouter/todos")
            assert len(response.json()) == 3

    @pytest.mark.asyncio
    async def test_openapi_docs(self) -> None:
        """Test OpenAPI docs."""

        @service()
        class MyRouter:
            router = Router()

            @router.get("/test")
            async def test(self) -> dict[str, str]:
                return {"status": "ok"}

        @module(services=[MyRouter])
        class MyApp:
            pass

        app = Canary(MyApp())
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
