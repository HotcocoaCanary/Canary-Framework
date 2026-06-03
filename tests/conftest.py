"""Pytest configuration and fixtures for Canary Framework tests."""

import pytest
from pydantic import BaseModel


@pytest.fixture
def sample_pydantic_model() -> type[BaseModel]:
    """Fixture for a sample Pydantic model."""

    class SampleModel(BaseModel):
        name: str
        value: int

    return SampleModel
