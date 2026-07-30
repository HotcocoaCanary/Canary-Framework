"""Contract tests for runnable examples."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.functional

EXAMPLES = tuple(
    sorted(Path(__file__).resolve().parents[2].joinpath("examples").glob("[0-9][0-9]_*.py"))
)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.name)
def test_example_uses_only_new_public_model(path: Path) -> None:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    assert "router = Router" not in source
    assert "services=" not in source
    assert "before_startup" not in source
    assert "before_shutdown" not in source
    assert "await app.init()" in source
    compile(tree, str(path), "exec")


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: path.name)
def test_example_imports_without_starting_server(path: Path) -> None:
    module_name = f"example_contract_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    assert isinstance(module, ModuleType)
    with patch("uvicorn.run") as run:
        spec.loader.exec_module(module)
    run.assert_not_called()
