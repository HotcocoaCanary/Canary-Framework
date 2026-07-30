"""Example 9: OpenAPI Documentation Customization.

Demonstrates: custom OpenAPI metadata, tags, summary/description,
multiple routers in one module generating a unified schema,
Swagger UI, ReDoc, OpenAPI JSON endpoints.
"""

from __future__ import annotations

import asyncio
from typing import cast

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import get, module, post, router
from canary_framework.common import CanaryConfig, ResponseSpec
from canary_framework.core import ModuleBase, RouterBase


class AppConfig(CanaryConfig):
    openapi_title: str = "Pet Store API"
    openapi_version: str = "1.0.0"
    openapi_description: str = "A sample pet store API built with Canary Framework"
    openapi_servers: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"url": "http://localhost:8000", "description": "Local server"},
        ]
    )
    openapi_security_schemes: dict[str, dict[str, object]] = Field(
        default_factory=lambda: cast(
            dict[str, dict[str, object]],
            {"apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
        )
    )


class Pet(BaseModel):
    id: int
    name: str = Field(description="Pet name")
    species: str = Field(description="Dog, cat, bird, etc.")
    age: int = Field(ge=0, le=30, description="Pet age in years")


class CreatePet(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    species: str
    age: int = Field(ge=0, le=30)


class ErrorResponse(BaseModel):
    error: str


@router(prefix="/pets", tags=("pets",), security=("apiKeyAuth",))
class PetRouter(RouterBase):
    _pets: dict[int, dict[str, object]]
    _next_id: int

    def __init__(self) -> None:
        super().__init__()
        self._pets = {}
        self._next_id = 1

    @get("/", summary="List all pets", response_model=list[Pet])
    async def list_pets(self) -> list[dict[str, object]]:
        return list(self._pets.values())

    @get(
        "/{pet_id}",
        summary="Get a pet by ID",
        description="Lookup a single pet and return 404 when missing.",
        response_model=Pet,
        deprecated=True,
        responses={404: ResponseSpec(description="Not found", model=ErrorResponse)},
    )
    async def get_pet(self, pet_id: int) -> dict[str, object] | tuple[dict[str, str], int]:
        pet = self._pets.get(pet_id)
        return pet if pet else ({"error": "Not found"}, 404)

    @post("/", summary="Create a new pet", response_model=Pet)
    async def create_pet(self, pet: CreatePet) -> dict[str, object]:
        new_id = self._next_id
        self._next_id += 1
        self._pets[new_id] = {"id": new_id, **pet.model_dump()}
        return self._pets[new_id]


@router(prefix="/system", tags=("system",))
class HealthRouter(RouterBase):
    @get("/health", summary="Health check")
    async def health(self) -> dict[str, str]:
        return {"status": "healthy"}


@module(config=AppConfig, children=(PetRouter, HealthRouter))
class App(ModuleBase):
    pass


async def setup() -> ModuleBase:
    app = App()
    await app.init()
    return app


if __name__ == "__main__":
    application = asyncio.run(setup())
    print("OpenAPI documentation available at:")
    print("  Swagger UI: http://127.0.0.1:8000/docs")
    print("  ReDoc:      http://127.0.0.1:8000/redoc")
    print("  OpenAPI JSON: http://127.0.0.1:8000/openapi.json")
    print("  Pet routes: /pets/, /pets/{id}")
    uvicorn.run(application, lifespan="on")
