import tomllib
from pathlib import Path
from typing import cast


def _dev_dependencies() -> list[str]:
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    return cast(list[str], pyproject["dependency-groups"]["dev"])


def test_dev_dependencies_include_starlette_testclient_backend() -> None:
    assert "httpx2>=2.0.0" in _dev_dependencies()


def test_dev_dependencies_include_pre_commit_runner() -> None:
    assert "pre-commit>=4.3.0" in _dev_dependencies()
