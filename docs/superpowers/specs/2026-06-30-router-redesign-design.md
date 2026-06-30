# Router 重设计 · 设计文档

- 日期：2026-06-30
- 状态：已确认骨架，待写实施计划
- 范围：`core/router/`、`core/service/_base.py`、`core/module/_base.py`、`engine/openapi.py`

## 1. 背景与目标

当前 router 机制把「声明 / 感知 / 聚合」三件事混在一起，导致：

- `asgi_app` 要分 standalone / mounted 两套路径分支；
- 路由聚合散在四处：`ServiceBase._collect_routes`、`_cf_collect_route_infos`、`_cf_get_root_routes`（service + module 各一份）、`ModuleBase.asgi_app` 里的 mount 去重；
- OpenAPI 被迫在 `startup()` 里硬生，并靠 `_cf_root_routes is None` 哨兵在多处懒触发；
- 一批请求处理 bug（详见 §6）。

根因只有一个：**parent 与 child 之间交换的「聚合货币」不统一**——有时传已建好的 ASGI 子应用（`Mount`），有时传裸 `RouteInfo`。

目标：用**单一聚合货币**重订 declare → perceive → aggregate 三段契约，使三个问题塌缩成一条干净管线，并顺手治本 §6 的请求处理 bug。

## 2. 核心决策

| # | 决策 | 取舍 |
|---|------|------|
| D1 | **聚合货币 = 结构化路由清单（descriptors）**，不是预建 ASGI mount | 统一 OpenAPI「免费」、消除 standalone/mounted 分支；代价是放弃 per-service ASGI 隔离/中间件（YAGNI，未来可加可选逃生口） |
| D2 | **组装时机 = 懒加载，单点记忆化** | 首次访问 `asgi_app` 时组装并缓存；产物时机确定、只有一处触发 |
| D3 | **声明 API 不变**：`router = Router(prefix, tags)` + `@router.get`；把「感知」形式化为 base 上的单一契约 | 用户零迁移；感知不再到处 `getattr+isinstance` |
| D4 | **prefix 完全显式**，无级联、无 `/{name}` 自动命名空间 | 最可预期；冲突在组装时报错 |

「service 本来就是 ASGI app」在 D1 下依然成立：它变成「**任一节点都能用自己的子树清单投影出一个 ASGI app**」，差别只在喂给同一个组装器的子树范围。

## 3. 架构：数据流

```
声明期 (import / 装饰器)
  @router.get(...) 在 class 的 Router 上累积静态 RouteInfo（handler 未绑 self）
        │
init() (同步)         DI 注入、实例化（不变）
        │
首次访问 asgi_app  ── root 节点单点记忆化组装 ──┐
        │                                      │
  _cf_collect_routes()  递归 fold 整棵子树     │
     · 叶 service：绑 self、拼 router.prefix    │
     · module：自身路由 + 原样拼接 children     │
        │                                      │
  得到 list[ResolvedRoute]（全路径、已绑 self）  │
        │                                      │
  _cf_assemble()                               │
     · 一次 build → Starlette 路由表            │
     · 同一份清单 → 一份 OpenAPI               │
     · 加 /docs /redoc /openapi.json（仅此一次）│
        └──────────► 缓存为 Assembled ◄────────┘
```

`startup()` / `shutdown()` 回归纯生命周期，不再碰路由或 OpenAPI。

## 4. 数据结构与契约

### 4.1 ResolvedRoute（聚合货币）

```python
@dataclass(slots=True)
class ResolvedRoute:
    full_path: str        # 本节点 router.prefix + route 路径，已拼好
    handler: Callable     # 已 __get__ 绑到 owning instance
    info: RouteInfo       # 静态元数据（models / tags / params / summary / ...）
```

### 4.2 感知 + 收集契约（取代四处聚合）

```python
class ServiceBase:
    def _get_router(self) -> Router | None:        # 已存在，唯一感知入口
        ...

    def _cf_collect_routes(self) -> list[ResolvedRoute]:
        """叶子 service：每条路由绑 self、拼 self.router.prefix。无 router 返回 []。"""

class ModuleBase(ServiceBase):
    def _cf_collect_routes(self) -> list[ResolvedRoute]:
        """module：自身路由 + 原样拼接每个 child 的 _cf_collect_routes()。"""
```

无 `inherited_prefix` 参数——D4 决定不级联，fold 即纯拼接。

### 4.3 组装 + 投影（单点记忆化）

```python
class Assembled(NamedTuple):
    router: StarletteRouter
    openapi: dict[str, object]

class ServiceBase:
    @property
    def asgi_app(self) -> StarletteRouter:
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.router

    def openapi(self) -> dict[str, object]:    # 想在 startup 导出 schema 调它，同一记忆化
        if self._cf_assembled is None:
            self._cf_assembled = self._cf_assemble()
        return self._cf_assembled.openapi

    def _cf_assemble(self) -> Assembled:
        resolved = self._cf_collect_routes()                       # 整棵子树，全路径
        _check_collisions(resolved)                                # (method, full_path) 重复 → 报错
        routes = [_build_route(r) for r in resolved]
        cfg = self.config or CanaryConfig()
        openapi = generate_openapi_schema(resolved, cfg)           # 同一份清单
        routes += _build_doc_routes(openapi, cfg)                  # 仅此一次
        return Assembled(StarletteRouter(routes), openapi)
```

`__call__` 简化为：lifespan → startup/shutdown；其余 → `asgi_app`。删除其中的 OpenAPI 生成与哨兵判断。

## 5. prefix 规则与行为变更

- `full_path = (本节点 router.prefix 或 "") + route 的相对路径`。
- 无 prefix → 路由落在（继承的）根上。
- **⚠️ 行为变更（唯一）**：删除「无 prefix 时自动挂 `/{ServiceName}`」（`get_mount_path` 的 `/{name}` 兜底）。前缀一律显式，路径冲突在组装时抛错。
  - 理由：现状 standalone 时无前缀服务在根、mounted 时在 `/{name}`，本身就不一致；显式前缀最可预期，且与 FastAPI `include_router(prefix=...)` 心智一致。

## 6. 请求处理重写（治本 5 个 bug）

endpoint builder 与 openapi 都要重写，借机修掉上一轮 review 确认的 bug：

| Bug | 现状 | 修复 |
|-----|------|------|
| #1 OpenAPI 全局缓存 | `_registered_schemas` 模块级全局，跨组装串味、`id()` 复用 | 降为 `_cf_assemble`/`generate_openapi_schema` 内的**局部** registry，每次组装从零 |
| #2 bool 转换 | 只认 `"true"`，`1/yes/on` 变 False | 常见 truthy/falsy 拼写（大小写无关）；无法识别 → 422 |
| #3 tuple 返回 | `(body, 404)` 被 `str()` 成 200 文本 | `_auto_response` 支持 `(body, status_code)`（自定义 header 用 `Response`） |
| #4 path+body → 500 | `handler(parsed, **kwargs)` 位置注入，body 非首参即冲突 | 声明期记下 body 参数名；运行期**全程按名传 kwargs**：`kwargs[body_name] = parsed` |
| #5 缺必填 query → 500 | 缺参直接漏掉 → handler 缺参崩 | 必填（无 default）缺失 → 422；可选缺失 → 省略让 handler default 兜底 |

附带：`_convert_param` 先 `unwrap_optional` 再按内层类型转换（修 `int | None` 不转换的不一致）。

endpoint 行为（伪码）：

```python
async def endpoint(request):
    kwargs, errors = {}, []
    for name in path_params:                 # 必在；转换失败 → 收集 error
        kwargs[name] = convert(request.path_params[name], type_of(name))
    for name in query_params:
        if name in request.query_params:
            kwargs[name] = convert(request.query_params[name], type_of(name))
        elif is_required(name):              # 无 default
            errors.append((name, "missing required query parameter"))
        # 可选且缺失：省略，由 handler 签名 default 兜底
    if errors:
        return JSONResponse({"detail": errors}, 422)
    if body_param:                           # 声明期捕获的名字
        kwargs[body_param] = model_cls(**await request.json())   # ValidationError → 422
    return _auto_response(await handler(**kwargs))               # 全部按名
```

## 7. 删除清单

- `ServiceBase._cf_get_root_routes`、`ModuleBase._cf_get_root_routes`
- `ServiceBase._cf_collect_route_infos`、`ServiceBase._cf_generate_openapi`
- `ServiceBase._collect_routes` 的 standalone/mounted 分叉、`_cf_root_routes` 哨兵
- `ModuleBase.asgi_app` 的 mount 去重逻辑、`ServiceBase.get_mount_path`
- `__call__` 内的 OpenAPI 生成分支
- `engine/openapi.py` 的模块级 `_registered_schemas`

净减代码。

## 8. YAGNI 边界（明确不做）

- ❌ module prefix 向下级联
- ❌ per-service 中间件 / 独立 ASGI 隔离（未来按需加「声明为 mount」逃生口）
- ❌ tuple 返回的 `(body, status, headers)` 三元组
- ❌ 重复 query 参数（`?a=1&a=2`）、list 型 query
- ❌ response_model 的输出校验/裁剪（仍仅用于文档；本次不改语义）

## 9. 测试计划

新增 functional 回归（堵住 5 个 bug 与 D4 行为）：

- path 参数 + body（body 非首参）→ 200 正确绑定
- 缺必填 query → 422；可选 query 缺失 → 用 default
- bool query：`1/true/yes/on` → True，`0/false/...` → False，乱值 → 422
- handler 返回 `(body, 404)` → 状态码 404
- 同进程**两次**组装 OpenAPI → 两份都自带完整 `components.schemas`（无悬空 `$ref`）
- 无 prefix 服务落在根；两个无 prefix 路由冲突 → 组装报错
- standalone 跑 service 与 module 装配同一 service → 路由表/openapi 一致

保持现有 152 测试通过（D4 去 `/{name}` 可能需调整依赖该行为的少数用例）。

## 10. 迁移影响

- 用户声明写法不变（D3）。
- 唯一对外行为变更：依赖 `/{name}` 自动命名空间的服务需显式补上 `Router(prefix=...)`。examples 与受影响测试随之更新。
