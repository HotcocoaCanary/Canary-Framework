"""分层：依赖方向必须严格单向。

这条测试把架构从"文档里的说法"变成"可执行的约束"：任何一次让 meta 反过来 import
flow 的改动，都会在这里失败。

扩展包（``test`` / ``config`` / ``web``）与 ``core`` 平级；``web.asgi`` 是协议层，它的两个
子包 ``app`` 与 ``server`` 各站协议的一侧。目录就是依赖关系，另有三条约束：只用核心的公开导出；子包可以依赖父包、
且只用父包的公开导出，父包不 import 子包，兄弟包互不依赖；顶层包不 import 它们——所以
``import canary_framework`` 始终不带入任何第三方包。
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "canary_framework"

# 层号越小越底层；一个模块只能 import 同层或更低层。
LAYERS = {
    "core.errors": 0,
    "core.meta": 1,
    "core.flow": 2,
    "core.canary": 3,
    "core": 4,
    "": 5,
    "test": 6,
    "config": 6,
    "web": 6,
    "web.asgi.protocol": 7,
    "web.asgi": 8,
    "web.asgi.server": 9,
    "web.asgi.app.http": 9,
    "web.asgi.app.routes": 10,
    "web.asgi.app.binding": 11,
    "web.asgi.app.router": 12,
    "web.asgi.app.app": 13,
    "web.asgi.app": 14,
}

#: 扩展包。带点的是子包：它可以依赖自己的各级父包，除此之外扩展包之间互不依赖。
EXTENSIONS = ("test", "config", "web", "web.asgi", "web.asgi.app", "web.asgi.server")


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


def _imports_with_names(path: pathlib.Path) -> list[tuple[str, list[str]]]:
    """每条 ``from canary_framework[.x] import a, b``：模块（去掉包名）与被 import 的名字。"""
    out = []
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("canary_framework")
        ):
            module = node.module.removeprefix("canary_framework").lstrip(".")
            out.append((module, [alias.name for alias in node.names]))
    return out


def _modules() -> list[tuple[str, pathlib.Path]]:
    return [
        (
            str(path.relative_to(ROOT).with_suffix("")).replace("/", ".").removesuffix(".__init__"),
            path,
        )
        for path in sorted(ROOT.rglob("*.py"))
    ]


def _extension(module: str) -> str | None:
    """模块所属的扩展包：最长前缀匹配，所以 ``web.asgi.app.router`` 属于 ``web.asgi.app``。"""
    owners = [e for e in EXTENSIONS if module == e or module.startswith(e + ".")]
    return max(owners, key=len, default=None)


def _parents(extension: str) -> set[str]:
    """各级父包：``web.asgi.app`` 的父包是 ``web`` 与 ``web.asgi``。"""
    parts = extension.split(".")
    return {".".join(parts[:i]) for i in range(1, len(parts))}


def test_no_module_imports_a_layer_above_itself() -> None:
    offenders = []
    for module, path in _modules():
        mine = _layer(module)
        for imported in _imports(path):
            if _layer(imported) > mine:
                offenders.append(f"{module} -> {imported}")
    assert offenders == []


def test_every_extension_is_on_disk() -> None:
    assert sorted(p.name for p in ROOT.iterdir() if p.is_dir() and p.name != "__pycache__") == [
        "config",
        "core",
        "test",
        "web",
    ]
    assert all((ROOT / extension.replace(".", "/")).is_dir() for extension in EXTENSIONS)


def test_extensions_use_only_public_exports_and_build_only_on_their_parents() -> None:
    """扩展包可以 import：自己包内的模块、``canary_framework.core``、自己的父包本身。

    后两者都只到包为止——``canary_framework.core.flow`` 或 ``canary_framework.web.asgi.protocol``
    是别人的内部。``from canary_framework import asgi`` 解析成 import 顶层包里的名字。
    """
    offenders = []
    for module, path in _modules():
        mine = _extension(module)
        if mine is None:
            continue
        allowed = {"core", *_parents(mine)}
        for imported, names in _imports_with_names(path):
            targets = names if imported == "" else [imported]
            for target in targets:
                if target not in allowed and _extension(target) != mine:
                    offenders.append(f"{module} -> {target}")
    assert offenders == []


def test_importing_the_package_loads_nothing_but_the_core() -> None:
    """``import canary_framework`` 不带入第三方包，也不带入任何扩展包。

    放在子进程里：本进程早已 import 过 FastAPI 与 pydantic。``canary_framework.test`` 只
    依赖核心，一并验证。标准库按安装位置判断：``sys.stdlib_module_names`` 不含
    ``_missing_stdlib_info`` 这类私有模块。
    """
    probe = (
        "import sys\n"
        "import sysconfig\n"
        "before = set(sys.modules)\n"
        "import canary_framework\n"
        "import canary_framework.test\n"
        "added = {name.split('.')[0] for name in set(sys.modules) - before}\n"
        "stdlib = sysconfig.get_path('stdlib')\n"
        "site = tuple(sysconfig.get_path(k) for k in ('purelib', 'platlib'))\n"
        "def bundled(name):\n"
        "    origin = getattr(sys.modules[name], '__file__', None) or ''\n"
        "    shipped = origin.startswith(stdlib) and not origin.startswith(site)\n"
        "    return name in sys.stdlib_module_names or shipped\n"
        "print(sorted(n for n in added - {'canary_framework'} if not bundled(n)))\n"
        "print(sorted(n for n in sys.modules if n.startswith('canary_framework.')"
        " and n.split('.')[1] in ('config', 'web')))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == ["[]", "[]"]
