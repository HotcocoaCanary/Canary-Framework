"""分层：依赖方向必须严格单向。

这条测试把架构从"文档里的说法"变成"可执行的约束"：任何一次让 declare 反过来 import
runtime 的改动，都会在这里失败。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = pytest.mark.unit

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "canary_framework"

# 层号越小越底层；一个模块只能 import 同层或更低层。
LAYERS = {
    "core.errors": 0,
    "core.declare": 1,
    "core.runtime": 2,
    "core.canary": 3,
    "core": 4,
    "": 5,
}


def _layer(module: str) -> int:
    """最长前缀匹配。"""
    best, found = -1, LAYERS[""]
    for prefix, depth in LAYERS.items():
        if (module == prefix or module.startswith(prefix + ".")) and len(prefix) > best:
            best, found = len(prefix), depth
    return found


def _imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("canary_framework")
        ):
            out.append(node.module.removeprefix("canary_framework").lstrip("."))
    return out


def test_no_module_imports_a_layer_above_itself() -> None:
    offenders = []
    for path in sorted(ROOT.rglob("*.py")):
        module = (
            str(path.relative_to(ROOT).with_suffix("")).replace("/", ".").removesuffix(".__init__")
        )
        mine = _layer(module)
        for imported in _imports(path):
            if _layer(imported) > mine:
                offenders.append(f"{module} -> {imported}")
    assert offenders == []
