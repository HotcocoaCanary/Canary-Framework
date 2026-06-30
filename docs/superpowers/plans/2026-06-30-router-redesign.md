# Router 重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用单一聚合货币（descriptors）重订 router 的 declare→perceive→aggregate 管线，并治本 5 个请求处理 bug。

**Architecture:** `@router.get` 在 class 上留静态 `RouteInfo`；每个节点经 `_cf_collect_routes()` 交出已绑 self、全路径的 `ResolvedRoute` 清单；module 原样拼接 children；被 run 的节点（root）首次访问 `asgi_app` 时单点记忆化地把整棵子树清单组装成一张 Starlette 路由表 + 一份 OpenAPI。

**Tech Stack:** Python 3.12+, Starlette, Pydantic v2, pytest（asyncio_mode=auto）, httpx/TestClient, uv。

设计依据：[docs/superpowers/specs/2026-06-30-router-redesign-design.md](../specs/2026-06-30-router-redesign-design.md)

## Global Constraints

- Python **3.12+** 语法；`from __future__ import annotations` 沿用现有风格。
- Docstring/注释 **双语（中文 + English）**。
- ruff line-length **100**，双引号；mypy **strict** on `src/`。
- 测试 `asyncio_mode=auto` —— **不要**写 `@pytest.mark.asyncio`；async 测试直接 `async def`。
- `uvicorn` 是 `[web]` 可选依赖，**禁止**在 `src/` 内 import。
- 公共符号一律经 `src/canary_framework/__init__.py` 的 imports **和** `__all__` 暴露。
- 每个任务结束跑 `uv run ruff check src/ tests/`、`uv run mypy src/ tests/`、相关 `uv run pytest`。
- 提交信息格式 `类型: 简短描述`（feat|fix|docs|refactor|test|chore）。

---

## File Structure

| 文件 | 职责 | 改动 |
|------|------|------|
| `src/canary_framework/common/types.py` | 共享类型 | 新增 `ResolvedRoute`；`RouteInfo` 加 `body_param` 字段 |
| `src/canary_framework/common/__init__.py` | common 再导出 | 导出 `ResolvedRoute` |
| `src/canary_framework/core/router/_utils.py` | 请求处理 | 重写 `_convert_param`、`_auto_response`、新增 `_build_route` + `_check_route_collisions`，删 `_route_handler` |
| `src/canary_framework/core/router/_base.py` | Router 容器 | 捕获 `body_param`；删 `_collect_routes` |
| `src/canary_framework/engine/openapi.py` | OpenAPI 生成 | 消费 `ResolvedRoute`、本地 schema registry（删全局） |
| `src/canary_framework/core/service/_base.py` | ServiceBase | 新增 `_cf_collect_routes`/`_cf_assemble`/`openapi`，重写 `asgi_app`/`__call__`，删一批死方法 |
| `src/canary_framework/core/module/_base.py` | ModuleBase | 重写 `_cf_collect_routes`（fold children），删 `asgi_app`/`_cf_get_root_routes` |
| `examples/*.py`, 受影响测试 | 迁移 | 去掉对 `/{name}` 的依赖 |

---

## Task 1: ResolvedRoute 类型 + RouteInfo.body_param 字段

**Files:**
- Modify: `src/canary_framework/common/types.py`
- Modify: `src/canary_framework/common/__init__.py`
- Test: `tests/unit/test_types.py`

**Interfaces:**
- Produces:
  - `ResolvedRoute(full_path: str, handler: Callable[..., object], info: RouteInfo)` —— `@dataclass(slots=True)`。
  - `RouteInfo.body_param: str | None = None` —— 请求体参数名（声明期捕获）。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_types.py` 末尾追加：

```python
def test_resolved_route_holds_full_path_and_handler():
    from canary_framework.common import ResolvedRoute, RouteInfo

    async def h() -> None: ...

    info = RouteInfo(
        handler=h, method="GET", path="/x", starlette_path="/x",
        path_params=[], query_params=[], param_meta={},
    )
    r = ResolvedRoute(full_path="/api/x", handler=h, info=info)
    assert r.full_path == "/api/x"
    assert r.info.method == "GET"


def test_route_info_body_param_defaults_none():
    from canary_framework.common import RouteInfo

    async def h() -> None: ...

    info = RouteInfo(
        handler=h, method="POST", path="/x", starlette_path="/x",
        path_params=[], query_params=[], param_meta={},
    )
    assert info.body_param is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_types.py::test_resolved_route_holds_full_path_and_handler tests/unit/test_types.py::test_route_info_body_param_defaults_none -v`
Expected: FAIL（`ImportError: cannot import name 'ResolvedRoute'` / `TypeError: unexpected keyword 'body_param'` 或 AttributeError）。

- [ ] **Step 3: 加字段与类型**

在 `src/canary_framework/common/types.py` 的 `RouteInfo` 内，于 `operation_id` 前后任意位置加字段（保持有默认值的字段在后）：

```python
    body_param: str | None = None
```

在 `RouteInfo` 定义之后新增：

```python
@dataclass(slots=True)
class ResolvedRoute:
    """已解析、可直接组装的单条路由（聚合货币）。

    full_path 已拼好前缀，handler 已绑定到拥有它的实例。

    A fully-resolved route ready for assembly (the aggregation currency).
    full_path is prefix-composed; handler is bound to its owning instance.
    """

    full_path: str
    handler: HookFunction
    info: RouteInfo
```

在 `types.py` 的 `__all__` 列表加入 `"ResolvedRoute"`（保持字母序）。

在 `src/canary_framework/common/__init__.py` 中，把 `ResolvedRoute` 加入从 `.types` 的 import 与该模块的 `__all__`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_types.py -v`
Expected: PASS。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/common/types.py src/canary_framework/common/__init__.py tests/unit/test_types.py
git commit -m "feat: 新增 ResolvedRoute 与 RouteInfo.body_param"
```

---

## Task 2: 修 `_convert_param`（bool + Optional）

**Files:**
- Modify: `src/canary_framework/core/router/_utils.py:62-80`
- Test: `tests/unit/test_router.py`

**Interfaces:**
- Consumes: 无新依赖。
- Produces: `_convert_param(value: str, param_type: type | None) -> object` —— bool 接受常见拼写、`Optional[T]` 先解包再转换；无法识别的 bool 抛 `ValueError`。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_router.py` 末尾追加：

```python
import pytest

from canary_framework.core.router._utils import _convert_param


@pytest.mark.parametrize("raw", ["1", "true", "True", "YES", "on"])
def test_convert_param_bool_truthy(raw):
    assert _convert_param(raw, bool) is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off"])
def test_convert_param_bool_falsy(raw):
    assert _convert_param(raw, bool) is False


def test_convert_param_bool_unrecognized_raises():
    with pytest.raises(ValueError):
        _convert_param("maybe", bool)


def test_convert_param_unwraps_optional_int():
    assert _convert_param("42", int | None) == 42
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_router.py -k convert_param -v`
Expected: FAIL（`'1'`→False、`int | None` 不转换、不抛 ValueError）。

- [ ] **Step 3: 重写 `_convert_param`**

把 `src/canary_framework/core/router/_utils.py` 的 `_convert_param` 整体替换为：

```python
_BOOL_TRUE = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSE = frozenset({"0", "false", "no", "off"})


def _convert_param(value: str, param_type: type | None) -> object:
    """将字符串参数转换为目标类型。

    解包 Optional[T] 后按内层类型转换；bool 接受常见真假拼写，
    无法识别时抛 ValueError（由调用方转 422）。

    Convert a string param to its target type. Unwraps Optional[T];
    bool accepts common spellings and raises ValueError on unrecognized input.
    """
    from canary_framework.common import unwrap_optional

    param_type, _ = unwrap_optional(param_type)
    if param_type is None or param_type is str:
        return value
    if param_type is bool:
        low = value.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")
    if param_type is int:
        return int(value)
    if param_type is float:
        return float(value)
    return value
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_router.py -k convert_param -v`
Expected: PASS。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/router/_utils.py tests/unit/test_router.py
git commit -m "fix: _convert_param 支持 bool 常见拼写与 Optional 解包"
```

---

## Task 3: 修 `_auto_response`（支持 `(body, status_code)`）

**Files:**
- Modify: `src/canary_framework/core/router/_utils.py:101-141`
- Test: `tests/unit/test_router.py`

**Interfaces:**
- Produces: `_auto_response(result: object) -> Response` —— 额外支持 `(body, status_code: int)` 二元组。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_router.py` 末尾追加：

```python
from canary_framework.core.router._utils import _auto_response


def test_auto_response_tuple_sets_status_code():
    resp = _auto_response(({"error": "Not found"}, 404))
    assert resp.status_code == 404
    assert b"Not found" in resp.body


def test_auto_response_plain_dict_is_200():
    resp = _auto_response({"ok": True})
    assert resp.status_code == 200
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_router.py -k auto_response -v`
Expected: FAIL（tuple 被 `str()` 成 200 PlainText）。

- [ ] **Step 3: 加 tuple 分支**

在 `src/canary_framework/core/router/_utils.py` 的 `_auto_response` 内，于 `if isinstance(result, Response):` 之后**最前面**插入：

```python
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], int)
    ):
        body, status_code = result
        if isinstance(body, Response):
            body.status_code = status_code
            return body
        if isinstance(body, BaseModel):
            return JSONResponse(body.model_dump(), status_code=status_code)
        if isinstance(body, (dict, list)):
            return JSONResponse(_convert_nested_models(body), status_code=status_code)
        if isinstance(body, str):
            return PlainTextResponse(body, status_code=status_code)
        return PlainTextResponse(str(body), status_code=status_code)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_router.py -k auto_response -v`
Expected: PASS。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/router/_utils.py tests/unit/test_router.py
git commit -m "fix: _auto_response 支持 (body, status_code) 元组返回"
```

---

## Task 4: Router 声明期捕获 `body_param`

**Files:**
- Modify: `src/canary_framework/core/router/_base.py:95-131`
- Test: `tests/unit/test_router_decorator.py`

**Interfaces:**
- Consumes: `RouteInfo.body_param`（Task 1）。
- Produces: 每个 `RouteInfo` 的 `body_param` 在声明期填好 —— 即「第一个既非 path 也非 query 的参数名」（有显式或自动 `request_model` 时）。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_router_decorator.py` 末尾追加：

```python
def test_router_captures_body_param_name():
    from pydantic import BaseModel

    from canary_framework.core.router import Router

    class Payload(BaseModel):
        name: str

    router = Router(prefix="/api")

    @router.put("/users/{user_id}")
    async def update(self, user_id: int, body: Payload) -> dict:
        return {}

    (info,) = router._route_infos
    assert info.body_param == "body"
    assert info.request_model is Payload
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_router_decorator.py::test_router_captures_body_param_name -v`
Expected: FAIL（`body_param` 为 None）。

- [ ] **Step 3: 在 `_http_method` 内捕获参数名**

在 `src/canary_framework/core/router/_base.py` 的 `decorator(fn)` 里，把现有 request_model 自动探测段替换为（同时算出 `body_param_name`）：

```python
            # Auto-detect request_model + 记录请求体参数名
            # Auto-detect request_model and capture the body parameter name.
            effective_request_model = request_model
            body_param_name: str | None = None
            for pname, (pann, _, _) in params.items():
                if pname in path_params or pname in query_params:
                    continue
                if effective_request_model is None:
                    if isinstance(pann, type) and issubclass(pann, BaseModel):
                        effective_request_model = pann
                        body_param_name = pname
                        break
                else:
                    body_param_name = pname
                    break
```

并在构造 `RouteInfo(...)` 时加入：

```python
                body_param=body_param_name,
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_router_decorator.py -v`
Expected: PASS。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/router/_base.py tests/unit/test_router_decorator.py
git commit -m "feat: Router 声明期捕获请求体参数名 body_param"
```

---

## Task 5: 重写 endpoint —— `_build_route(resolved)`（按名传参 + 必填 query 422）

**Files:**
- Modify: `src/canary_framework/core/router/_utils.py`（替换 `_route_handler` 为 `_build_route`）
- Test: `tests/functional/test_request_binding.py`（新建）

**Interfaces:**
- Consumes: `ResolvedRoute`（Task 1）、`_convert_param`（Task 2）、`_auto_response`（Task 3）、`RouteInfo.body_param`（Task 4）。
- Produces:
  - `_build_route(resolved: ResolvedRoute) -> Route` —— 从 `ResolvedRoute` 建 Starlette `Route`，全程按参数名传 kwargs。
  - `_check_route_collisions(routes: list[ResolvedRoute]) -> None` —— `(method, full_path)` 重复抛 `ValueError`。
  - 行为：path 参数转换失败→400；必填（无 default）query 缺失或转换失败→422；可选 query 缺失→省略（由 handler 签名 default 兜底）；body 校验失败→422。

- [ ] **Step 1: 写失败测试**

新建 `tests/functional/test_request_binding.py`：

```python
"""Request binding regression tests (path+body, required query, etc.)."""

import pytest
from pydantic import BaseModel
from starlette.testclient import TestClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

pytestmark = pytest.mark.functional


class Patch(BaseModel):
    name: str


@service()
class Api(ServiceBase):
    router = Router(prefix="/api")

    @router.put("/users/{user_id}")
    async def update(self, user_id: int, body: Patch) -> dict:
        return {"user_id": user_id, "name": body.name}

    @router.get("/feature?enabled={flag}")
    async def feature(self, flag: bool) -> dict:
        return {"enabled": flag}

    @router.get("/search?q={query}")
    async def search(self, query: str = "none") -> dict:
        return {"query": query}


@module(services=[Api])
class App(ModuleBase):
    pass


def _client() -> TestClient:
    app = App()
    app.init()
    return TestClient(app)


def test_path_param_plus_body_binds_by_name():
    with _client() as c:
        r = c.put("/api/users/7", json={"name": "neo"})
        assert r.status_code == 200
        assert r.json() == {"user_id": 7, "name": "neo"}


def test_missing_required_query_returns_422():
    with _client() as c:
        assert c.get("/api/feature").status_code == 422


def test_bool_query_one_is_true():
    with _client() as c:
        assert c.get("/api/feature?enabled=1").json() == {"enabled": True}


def test_optional_query_uses_default():
    with _client() as c:
        assert c.get("/api/search").json() == {"query": "none"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/functional/test_request_binding.py -v`
Expected: FAIL —— 此刻 `_build_route` 尚不存在，且现有装配链路仍走旧逻辑（path+body 会 500）。

- [ ] **Step 3: 用 `_build_route` 替换 `_route_handler`**

在 `src/canary_framework/core/router/_utils.py`，删除 `_route_handler` 整个函数，新增：

```python
def _check_route_collisions(routes: list[ResolvedRoute]) -> None:
    """检测 (method, full_path) 冲突，重复则抛错。

    Detect duplicate (method, full_path) routes and raise on collision.
    """
    seen: set[tuple[str, str]] = set()
    for r in routes:
        key = (r.info.method, r.full_path)
        if key in seen:
            raise ValueError(f"Route collision: {r.info.method} {r.full_path}")
        seen.add(key)


def _build_route(resolved: ResolvedRoute) -> Route:
    """从 ResolvedRoute 构建 Starlette Route，全程按参数名绑定。

    Build a Starlette Route from a ResolvedRoute, binding everything by name.
    """
    info = resolved.info
    handler = cast("Callable[..., Awaitable[object]]", resolved.handler)
    param_types: dict[str, type | None] = {
        name: cast("type | None", meta[0])  # type: ignore[index]
        for name, meta in info.param_meta.items()
    }

    def _required(name: str) -> bool:
        meta = info.param_meta.get(name)
        return not (meta and meta[1])  # type: ignore[index]

    async def endpoint(request: Request) -> Response:
        kwargs: dict[str, object] = {}
        errors: list[dict[str, str]] = []

        for name in info.path_params:
            if name in request.path_params:
                try:
                    kwargs[name] = _convert_param(request.path_params[name], param_types.get(name))
                except (ValueError, TypeError):
                    return JSONResponse(
                        {"detail": f"Invalid value for path parameter '{name}'"},
                        status_code=400,
                    )

        for name in info.query_params:
            if name in request.query_params:
                try:
                    kwargs[name] = _convert_param(request.query_params[name], param_types.get(name))
                except (ValueError, TypeError):
                    errors.append({"param": name, "msg": "invalid value"})
            elif _required(name):
                errors.append({"param": name, "msg": "missing required query parameter"})

        if errors:
            return JSONResponse({"detail": errors}, status_code=422)

        if info.request_model is not None and info.body_param is not None:
            try:
                body = cast("dict[str, object]", await request.json())
            except Exception:
                return JSONResponse({"detail": "Invalid JSON body"}, status_code=400)
            model_cls = cast("type[BaseModel]", info.request_model)
            try:
                kwargs[info.body_param] = model_cls(**body)
            except ValidationError as e:
                return JSONResponse({"detail": e.errors()}, status_code=422)

        return _auto_response(await handler(**kwargs))

    return Route(resolved.full_path, endpoint=endpoint, methods=[info.method])
```

在文件顶部 import 区加入 `from canary_framework.common import ResolvedRoute, RouteInfo`（若 `RouteInfo` 已 import 则合并），并更新 `__all__`：移除 `"_route_handler"`，加入 `"_build_route"`、`"_check_route_collisions"`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/functional/test_request_binding.py -v`
Expected: 仍可能 FAIL —— 旧装配链路（`_collect_routes`/`ModuleBase.asgi_app`）还在用 `_route_handler`。**先确认编译/导入层面**：

Run: `uv run python -c "from canary_framework.core.router._utils import _build_route, _check_route_collisions"`
Expected: 无报错。

> 说明：本任务交付 `_build_route` 函数本身；端到端绿灯依赖 Task 8 接上装配链路。Task 8 会回到此测试文件验证全绿。此处先用单元方式验证 `_build_route`：

在 `tests/functional/test_request_binding.py` 末尾追加一个直连测试：

```python
def test_build_route_direct_path_and_body():
    from starlette.applications import Starlette
    from canary_framework.common import ResolvedRoute
    from canary_framework.core.router._utils import _build_route

    api = Api()
    (info,) = [i for i in Api.router._route_infos if i.method == "PUT"]
    bound = info.handler.__get__(api, Api)
    route = _build_route(ResolvedRoute(full_path="/api/users/{user_id}", handler=bound, info=info))
    app = Starlette(routes=[route])
    with TestClient(app) as c:
        assert c.put("/api/users/9", json={"name": "trinity"}).json() == {
            "user_id": 9, "name": "trinity",
        }
```

Run: `uv run pytest tests/functional/test_request_binding.py::test_build_route_direct_path_and_body -v`
Expected: PASS。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/router/_utils.py tests/functional/test_request_binding.py
git commit -m "feat: _build_route 按名绑定参数, 必填 query 缺失返回 422"
```

---

## Task 6: `_cf_collect_routes` —— 感知 + 收集契约

**Files:**
- Modify: `src/canary_framework/core/service/_base.py`（加 `_cf_collect_routes`）
- Modify: `src/canary_framework/core/module/_base.py`（override `_cf_collect_routes`）
- Test: `tests/integration/test_route_collection.py`（新建）

> **本任务纯增量**：只新增 `_cf_collect_routes`，**不**删除 `_collect_routes`、**不**改动旧 `asgi_app`。旧的 serving 路径保持工作、现有测试保持绿；`_collect_routes` 的删除与 `asgi_app` 重写在 Task 8 一并完成。

**Interfaces:**
- Consumes: `ResolvedRoute`（Task 1）。
- Produces:
  - `ServiceBase._cf_collect_routes(self) -> list[ResolvedRoute]` —— 叶子：每条路由绑 self、`full_path = router.prefix + starlette_path`；无 router 返回 `[]`。
  - `ModuleBase._cf_collect_routes(self) -> list[ResolvedRoute]` —— 自身路由 + 原样拼接每个 child 的结果。

- [ ] **Step 1: 写失败测试**

新建 `tests/integration/test_route_collection.py`：

```python
"""Route collection (perception + fold) tests."""

import pytest

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

pytestmark = pytest.mark.integration


@service()
class Users(ServiceBase):
    router = Router(prefix="/users")

    @router.get("/{uid}")
    async def get(self, uid: int) -> dict:
        return {"uid": uid}


@service()
class Orders(ServiceBase):
    router = Router(prefix="/orders")

    @router.get("/")
    async def list(self) -> list:
        return []


@module(services=[Users, Orders])
class App(ModuleBase):
    pass


def test_leaf_service_collects_with_prefix():
    u = Users()
    routes = u._cf_collect_routes()
    assert [r.full_path for r in routes] == ["/users/{uid}"]


def test_module_folds_children():
    app = App()
    app.init()
    paths = sorted(r.full_path for r in app._cf_collect_routes())
    assert paths == ["/orders/", "/users/{uid}"]


def test_collected_handler_is_bound():
    u = Users()
    (r,) = u._cf_collect_routes()
    # 绑定后无需再传 self / 可访问实例
    assert r.handler.__self__ is u
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/integration/test_route_collection.py -v`
Expected: FAIL（`AttributeError: '_cf_collect_routes'`）。

- [ ] **Step 3: 实现 ServiceBase 叶子版本**

在 `src/canary_framework/core/service/_base.py` 顶部 import 区加：

```python
from types import FunctionType

from canary_framework.common import ResolvedRoute
```

在 `ServiceBase` 内新增方法（放在 `_get_router` 之后）：

```python
    def _cf_collect_routes(self) -> list[ResolvedRoute]:
        """收集本服务的路由贡献：绑 self、拼 router.prefix。

        Collect this service's route contribution: bound to self,
        prefixed with router.prefix. Returns [] when no router.
        """
        router = self._get_router()
        if router is None:
            return []
        cls = type(self)
        out: list[ResolvedRoute] = []
        for info in router._route_infos:
            bound = cast(FunctionType, info.handler).__get__(self, cls)
            out.append(
                ResolvedRoute(
                    full_path=router.prefix + info.starlette_path,
                    handler=bound,
                    info=info,
                )
            )
        return out
```

（`cast` 已在该文件 import；若无则从 `typing` 补 import。）

- [ ] **Step 4: 实现 ModuleBase fold 版本**

在 `src/canary_framework/core/module/_base.py` 顶部 import 区加 `from canary_framework.common import ResolvedRoute`（与现有 common import 合并）。在 `ModuleBase` 内新增：

```python
    @override
    def _cf_collect_routes(self) -> list[ResolvedRoute]:
        """模块路由贡献 = 自身路由 + 原样拼接每个子服务的贡献。

        Module contribution = own routes + children's routes concatenated.
        """
        out: list[ResolvedRoute] = list(super()._cf_collect_routes())
        for _, child in self._iter_instances(skip_none=True):
            collect = getattr(child, "_cf_collect_routes", None)
            if collect is not None:
                out.extend(collect())
        return out
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/integration/test_route_collection.py -v`
Expected: PASS。

并确认未破坏现有套件（本任务纯增量、旧 serving 路径未动）：
Run: `uv run pytest -q`
Expected: 全 PASS。

- [ ] **Step 6: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/service/_base.py src/canary_framework/core/module/_base.py tests/integration/test_route_collection.py
git commit -m "feat: _cf_collect_routes 统一感知与聚合 (service 叶 + module fold)"
```

---

## Task 7: OpenAPI 消费 ResolvedRoute + 本地 schema registry

**Files:**
- Modify: `src/canary_framework/engine/openapi.py`
- Test: `tests/unit/test_openapi.py`

**Interfaces:**
- Consumes: `ResolvedRoute`（Task 1）。
- Produces: `generate_openapi_schema(routes: list[ResolvedRoute], *, title="Canary Framework API", version="1.0.0", description="", servers=None, security_schemes=None) -> dict[str, object]` —— 用 `r.full_path` + `r.info`；schema registry 为**调用内局部**（删全局 `_registered_schemas`），重复调用各自完整。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_openapi.py` 末尾追加：

```python
def test_openapi_two_generations_each_have_components():
    from pydantic import BaseModel

    from canary_framework.common import ResolvedRoute, RouteInfo
    from canary_framework.engine.openapi import generate_openapi_schema

    class Item(BaseModel):
        x: int

    async def h(self, body: Item) -> dict:
        return {}

    info = RouteInfo(
        handler=h, method="POST", path="/i", starlette_path="/i",
        path_params=[], query_params=[], param_meta={}, request_model=Item, body_param="body",
    )
    routes = [ResolvedRoute(full_path="/api/i", handler=h, info=info)]

    doc1 = generate_openapi_schema(routes)
    doc2 = generate_openapi_schema(routes)

    for doc in (doc1, doc2):
        ref = doc["paths"]["/api/i"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        name = ref.split("/")[-1]
        assert name in doc["components"]["schemas"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_openapi.py::test_openapi_two_generations_each_have_components -v`
Expected: FAIL（旧签名收 `list[RouteInfo]`，且第二次 `components.schemas` 为空 → KeyError/断言失败）。

- [ ] **Step 3: 局部化 registry 并改签名**

在 `src/canary_framework/engine/openapi.py`：

1. 删除模块级 `_registered_schemas: dict[int, str] = {}`。
2. `_build_model_schema` 增加参数 `registered: dict[int, str]`，把函数体内对全局 `_registered_schemas` 的引用改为该参数；递归调用 `_build_model_schema(args[0], schemas_dict, registered)` 一并传入。
3. import 区加 `from canary_framework.common import ResolvedRoute`（与现有 common import 合并）。
4. 把 `generate_openapi_schema` 改为消费 `ResolvedRoute`：

```python
def generate_openapi_schema(
    routes: list[ResolvedRoute],
    title: str = "Canary Framework API",
    version: str = "1.0.0",
    description: str = "",
    servers: list[dict[str, str]] | None = None,
    security_schemes: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """从 ResolvedRoute 列表生成 OpenAPI 3.0.3 schema。"""
    registered: dict[int, str] = {}
    schema: dict[str, object] = {
        "openapi": "3.0.3",
        "info": {"title": title, "version": version},
        "paths": {},
        "components": {"schemas": {}},
    }
    if description:
        cast("dict[str, object]", schema["info"])["description"] = description
    if servers:
        schema["servers"] = servers
    components = cast("dict[str, object]", schema["components"])
    if security_schemes:
        components["securitySchemes"] = security_schemes
    schemas_dict = cast("dict[str, object]", components["schemas"])
    paths = cast("dict[str, object]", schema["paths"])

    for resolved in routes:
        info = resolved.info
        starlette_path = resolved.full_path
        while "//" in starlette_path:
            starlette_path = starlette_path.replace("//", "/")

        operation: dict[str, object] = {}
        if info.summary:
            operation["summary"] = info.summary
        if info.description:
            operation["description"] = info.description
        if info.deprecated:
            operation["deprecated"] = info.deprecated
        if info.operation_id:
            operation["operationId"] = info.operation_id

        merged_tags = list(dict.fromkeys(info.router_tags + info.tags))
        if merged_tags:
            operation["tags"] = merged_tags

        parameters: list[dict[str, object]] = []
        for param_name in info.path_params:
            entry = info.param_meta.get(param_name, (str, False, None))
            parameters.append({
                "name": param_name, "in": "path", "required": True,
                "schema": _build_parameter_schema(entry[0], entry[2]),  # type: ignore[index]
            })
        for param_name in info.query_params:
            entry = info.param_meta.get(param_name, (str, False, None))
            parameters.append({
                "name": param_name, "in": "query", "required": not entry[1],  # type: ignore[index]
                "schema": _build_parameter_schema(entry[0], entry[2]),  # type: ignore[index]
            })
        if parameters:
            operation["parameters"] = parameters

        if info.request_model is not None:
            request_schema = _build_model_schema(info.request_model, schemas_dict, registered)
            operation["requestBody"] = {
                "description": getattr(info.request_model, "__doc__", "") or "",
                "content": {"application/json": {"schema": request_schema}},
            }

        responses: dict[str, object] = dict(info.responses)
        if info.response_model is not None:
            response_schema = _build_model_schema(info.response_model, schemas_dict, registered)
            if "200" not in responses:
                responses["200"] = {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": response_schema}},
                }
        operation["responses"] = responses

        _ = paths.setdefault(starlette_path, {})
        cast("dict[str, object]", paths[starlette_path])[info.method.lower()] = operation

    return schema
```

- [ ] **Step 4: 修现有 openapi 测试的输入类型**

`tests/unit/test_openapi.py` 中现有用例若直接给 `generate_openapi_schema` 传 `RouteInfo` 列表，需包成 `ResolvedRoute(full_path=<router_prefix+starlette_path>, handler=<info.handler>, info=<info>)`。逐个改造调用点（保持各用例断言不变）。

Run: `uv run pytest tests/unit/test_openapi.py -v`
Expected: PASS（含新用例）。

- [ ] **Step 5: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/engine/openapi.py tests/unit/test_openapi.py
git commit -m "fix: OpenAPI 消费 ResolvedRoute 且 schema registry 局部化 (修全局缓存泄漏)"
```

---

## Task 8: 单点记忆化组装 —— `_cf_assemble` / `asgi_app` / `openapi()`，删死代码

**Files:**
- Modify: `src/canary_framework/core/service/_base.py`
- Modify: `src/canary_framework/core/module/_base.py`
- Modify: `src/canary_framework/core/router/_base.py`（删 `_collect_routes`，Task 6 已不再删）
- Test: `tests/functional/test_request_binding.py`（接通端到端）、`tests/functional/test_assembly.py`（新建）

**Interfaces:**
- Consumes: `_cf_collect_routes`（Task 6）、`_build_route`/`_check_route_collisions`（Task 5）、`generate_openapi_schema`（Task 7）、`_build_doc_routes`（现有）。
- Produces:
  - `ServiceBase.asgi_app -> StarletteRouter`（记忆化）。
  - `ServiceBase.openapi() -> dict[str, object]`（同一记忆化）。
  - `ServiceBase._cf_assemble() -> Assembled`，`Assembled = NamedTuple(router=StarletteRouter, openapi=dict[str, object])`。

- [ ] **Step 1: 写失败测试**

新建 `tests/functional/test_assembly.py`：

```python
"""Single-point assembly: standalone == mounted, docs present, collision."""

import pytest
from starlette.testclient import TestClient

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase

pytestmark = pytest.mark.functional


@service()
class Hello(ServiceBase):
    router = Router(prefix="/hello")

    @router.get("/")
    async def hi(self) -> dict:
        return {"msg": "hi"}


@module(services=[Hello])
class App(ModuleBase):
    pass


def test_standalone_service_serves_and_has_docs():
    svc = Hello()
    svc.init()
    with TestClient(svc) as c:
        assert c.get("/hello/").json() == {"msg": "hi"}
        assert c.get("/openapi.json").status_code == 200


def test_module_serves_same_paths_as_standalone():
    app = App()
    app.init()
    with TestClient(app) as c:
        assert c.get("/hello/").json() == {"msg": "hi"}
        assert "/hello/" in c.get("/openapi.json").json()["paths"]


def test_openapi_method_returns_same_dict():
    app = App()
    app.init()
    assert "/hello/" in app.openapi()["paths"]


def test_no_prefix_collision_raises():
    @service()
    class A(ServiceBase):
        router = Router()

        @router.get("/x")
        async def a(self) -> dict:
            return {}

    @service()
    class B(ServiceBase):
        router = Router()

        @router.get("/x")
        async def b(self) -> dict:
            return {}

    @module(services=[A, B])
    class Bad(ModuleBase):
        pass

    bad = Bad()
    bad.init()
    with pytest.raises(ValueError, match="collision"):
        _ = bad.asgi_app
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/functional/test_assembly.py -v`
Expected: FAIL（`asgi_app` 仍是 Task 6 的 `NotImplementedError` 占位）。

- [ ] **Step 3: 重写 ServiceBase 组装与入口**

在 `src/canary_framework/core/service/_base.py`：

1. import 区加：

```python
from typing import NamedTuple

from canary_framework.core.router._utils import _build_route, _check_route_collisions
from canary_framework.engine.openapi import generate_openapi_schema
```

并确保已 import `_build_doc_routes`（来自 `canary_framework.core.router`，现有 import 保留）。

2. 在 `ServiceBase` 类上方加：

```python
class Assembled(NamedTuple):
    """组装产物：路由表 + OpenAPI。Assembly product: router + openapi."""

    router: StarletteRouter
    openapi: dict[str, object]
```

3. `__init__` 中，把 `self._starlette_router` 与 `self._cf_root_routes` 两行替换为：

```python
        self._cf_assembled: Assembled | None = None
```

4. 把 `asgi_app` property 体替换为：

```python
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.router
```

5. 新增方法：

```python
    def openapi(self) -> dict[str, object]:
        """返回本（子）树的 OpenAPI 文档（记忆化）。

        Return the OpenAPI document for this (sub)tree (memoized).
        """
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.openapi

    def _cf_assemble(self) -> Assembled:
        """单点记忆化组装：收集 → 校验冲突 → 建路由表 + OpenAPI + 文档端点。

        Single-point assembly: collect → check collisions → build the routing
        table, OpenAPI document, and doc endpoints.
        """
        resolved = self._cf_collect_routes()
        if not resolved:
            return Assembled(StarletteRouter([]), {})
        _check_route_collisions(resolved)
        cfg = self.config or CanaryConfig()
        routes: list[Route] = [_build_route(r) for r in resolved]
        openapi = generate_openapi_schema(
            resolved,
            title=cfg.openapi_title,
            version=cfg.openapi_version,
            description=cfg.openapi_description,
            servers=cfg.openapi_servers or None,
            security_schemes=cfg.openapi_security_schemes or None,
        )
        routes += _build_doc_routes(
            openapi,
            openapi_path=cfg.docs_openapi_path,
            swagger_path=cfg.docs_swagger_path,
            redoc_path=cfg.docs_redoc_path,
            swagger_css=cfg.docs_swagger_css_cdn,
            swagger_js=cfg.docs_swagger_js_cdn,
            redoc_js=cfg.docs_redoc_cdn,
        )
        return Assembled(StarletteRouter(routes), openapi)
```

6. 把 `__call__` 体替换为：

```python
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        else:
            await self.asgi_app(scope, receive, send)
```

7. `startup()` 删除 `if self._cf_parent_registry is None: await self._cf_generate_openapi()` 两行（保留 hook 调用）。

8. 删除以下方法/属性：`get_mount_path`、`_cf_get_root_routes`、`_cf_collect_route_infos`、`_cf_generate_openapi`。删除不再使用的 import（`RouteInfo` 若仅这些用到、`CF_NAME_ATTR`、`_collect_routes`）。

- [ ] **Step 4: 精简 ModuleBase 并删除旧 `_collect_routes`**

在 `src/canary_framework/core/module/_base.py`：

1. 删除整个 `asgi_app` property（继承 `ServiceBase.asgi_app`）。
2. 删除 `_cf_get_root_routes` 方法。
3. 删除随之不再使用的 import：`Mount`、`Route`、`StarletteRouter`（如其它处仍用到 `Route` 则保留）、`_collect_routes`、`ASGIApp`、`cast`（按实际使用情况收敛，以 ruff 为准）。

在 `src/canary_framework/core/router/_base.py`：

4. 删除 `_collect_routes` 函数及其在 `__all__` 的条目（保留 `Router`）。此时已无任何引用（service/module 的旧 `asgi_app` 已在本任务删除）。

- [ ] **Step 5: 跑端到端测试**

Run: `uv run pytest tests/functional/test_assembly.py tests/functional/test_request_binding.py -v`
Expected: 全 PASS（含 Task 5 中先前依赖装配链路的 4 个用例）。

- [ ] **Step 6: 类型检查 + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/ tests/
git add src/canary_framework/core/service/_base.py src/canary_framework/core/module/_base.py src/canary_framework/core/router/_base.py tests/functional/test_assembly.py
git commit -m "refactor: 单点记忆化组装 asgi_app/openapi, 删除分散聚合与 standalone/mounted 分支"
```

---

## Task 9: 迁移 examples 与受 `/{name}` 影响的测试

**Files:**
- Modify: 受影响的 `examples/*.py`、`tests/functional/*.py`、`tests/integration/*.py`
- 修正 examples 07/08 的错误示例（tuple 404、`enabled=1`）

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 全套测试在新行为下绿灯；examples 反映正确用法。

- [ ] **Step 1: 跑全量测试，列出失败**

Run: `uv run pytest -q`
Expected: 仅剩依赖旧行为（`/{name}` 自动命名空间、tuple/bool 旧语义）的用例失败。**记录失败清单**。

- [ ] **Step 2: 逐个修正失败用例**

对每个失败用例判断成因并改：
- 依赖无 prefix 服务挂在 `/{ServiceName}` 的：给该服务的 `Router` 补显式 `prefix=`，或把断言路径改为新（显式前缀）路径。
- 依赖 `(body, 404)` 旧 200 文本行为的：改断言为 404（新行为）。
- 依赖 `enabled=1`→False 的：改断言为 True。

> 不要为「保留旧行为」而改源码 —— 新行为是设计目标（spec §5/§6）。

- [ ] **Step 3: 修正 examples 07/08**

- `examples/07_validation.py`：`get_user` 找不到时由 `return {"error": "Not found"}, 404` 保持不变（现在 Task 3 已使其真正返回 404）；在文件顶部注释确认该行为。
- `examples/08_parameters.py`：确认 `feature?enabled=1` 注释成立（Task 2 已使其为 True）；若有无 prefix 依赖则补 `Router(prefix=...)`。

- [ ] **Step 4: 全量绿灯**

Run: `uv run pytest -q`
Expected: 全 PASS。

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ tests/`
Expected: 无错误。

- [ ] **Step 5: 提交**

```bash
git add examples/ tests/
git commit -m "test: 迁移用例至显式前缀与修复后的请求处理语义"
```

---

## Self-Review

**1. Spec coverage（spec → task 映射）**

- D1 descriptors 货币 → Task 1（ResolvedRoute）、Task 6（collect）。
- D2 懒加载单点记忆化 → Task 8（`_cf_assemble`/`asgi_app`/`openapi()`）。
- D3 声明 API 不变 + 感知形式化 → Task 6（`_cf_collect_routes` 经 `_get_router`）。
- D4 显式前缀、去 `/{name}`、冲突报错 → Task 6（full_path）、Task 5（`_check_route_collisions`）、Task 8（标准入口）、Task 9（迁移）。
- §6 bug #1 → Task 7；#2 → Task 2；#3 → Task 3；#4 → Task 4+5；#5 → Task 5。
- §7 删除清单 → Task 6（`_collect_routes`）、Task 8（其余）。
- §9 测试计划 → Task 5/6/7/8/9 各对应用例。

无遗漏。

**2. Placeholder scan**：Task 6 Step 5 / Task 8 的 `NotImplementedError` 是**显式的过渡占位**，于 Task 8 Step 3 被真实实现替换 —— 非计划占位，已标注存活范围。其余步骤均含完整代码/命令。

**3. Type consistency**：`_cf_collect_routes()`（无参）、`_build_route(resolved)`、`generate_openapi_schema(routes, ...)`、`Assembled(router, openapi)`、`RouteInfo.body_param` 在各任务签名一致。`_route_handler` 已于 Task 5 删除并替换为 `_build_route`，无残留引用（Task 8 Step 3.8 清理 import）。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-30-router-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个任务派新 subagent，任务间双阶段审查，迭代快。

**2. Inline Execution** — 本会话内分批执行、检查点审查。

**Which approach?**
