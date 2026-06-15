"""Example 9: OpenAPI Documentation Customization.

Demonstrates: custom OpenAPI metadata, tags, summary/description,
multiple routers in one module generating a unified schema,
Swagger UI, ReDoc, OpenAPI JSON endpoints.
"""

import uvicorn
from pydantic import BaseModel, Field

from canary_framework import config, module, service
from canary_framework.common.config import CanaryConfig
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


# ── Config ───────────────────────────────────────────────
@config()
class AppConfig(CanaryConfig):
    openapi_title: str = "Pet Store API"
    openapi_version: str = "1.0.0"
    openapi_description: str = "A sample pet store API built with Canary Framework"
    openapi_servers: list[dict] = [
        {"url": "http://localhost:8000", "description": "Local server"},
    ]


# ── Models ───────────────────────────────────────────────
class Pet(BaseModel):
    id: int
    name: str = Field(description="Pet name")
    species: str = Field(description="Dog, cat, bird, etc.")
    age: int = Field(ge=0, le=30, description="Pet age in years")


class CreatePet(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    species: str
    age: int = Field(ge=0, le=30)


# ── Pet Service ──────────────────────────────────────────
@service()
class PetService(ServiceBase):
    router = Router(prefix="/pets", tags=["pets"])
    _pets: dict[int, dict] = {}
    _next_id: int = 1

    @router.get("/", summary="List all pets", response_model=list[Pet])
    async def list_pets(self) -> list[dict]:
        return list(self._pets.values())

    @router.get("/{pet_id}", summary="Get a pet by ID", response_model=Pet)
    async def get_pet(self, pet_id: int) -> dict | tuple:
        pet = self._pets.get(pet_id)
        return pet if pet else ({"error": "Not found"}, 404)

    @router.post("/", summary="Create a new pet", response_model=Pet)
    async def create_pet(self, pet: CreatePet) -> dict:
        new_id = self._next_id
        self._next_id += 1
        self._pets[new_id] = {"id": new_id, **pet.model_dump()}
        return self._pets[new_id]


# ── Health Service ───────────────────────────────────────
@service()
class HealthService(ServiceBase):
    router = Router(tags=["system"])

    @router.get("/health", summary="Health check")
    async def health(self) -> dict:
        return {"status": "healthy"}


# ── Root Module ──────────────────────────────────────────
@module(config=AppConfig, services=[PetService, HealthService])
class App(ModuleBase):
    pass


if __name__ == "__main__":
    app = App()
    app.init()
    print("OpenAPI documentation available at:")
    print("  Swagger UI: http://127.0.0.1:8000/docs")
    print("  ReDoc:      http://127.0.0.1:8000/redoc")
    print("  OpenAPI JSON: http://127.0.0.1:8000/openapi.json")
    print("  Pet routes: /pets/, /pets/{id}")
    uvicorn.run(app, lifespan="on")
