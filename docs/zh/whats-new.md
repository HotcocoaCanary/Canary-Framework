# What's New in 0.5.x

本页总结 `0.5.2` 版本线中的 router 重设计与请求处理修复，以及你的代码是否需要相应调整。

!!! tip "延伸阅读"
    本页是概览。完整内部机制见[架构与内部机制](core.md)；日常路由用法见 [HTTP 路由](web.md)；
    下文提到的配置字段见[配置](configuration.md)。

## Router 重设计：单点记忆化组装

在 `0.5.2` 之前，路由聚合、OpenAPI 生成与文档端点注册分散在多处代码路径中，且 service 独立运行与
在 module 中被组合时走的是不同分支。这些分支现已全部消失。

=== "心智模型 — 之前"

    ```
    独立运行的 service   ──►  一套组装路径   ──►  路由 + 文档
    被 module 组合的 service ──►  另一套组装路径 ──►  路由 + 文档
                             (挂载至 /{ServiceName}，首个 router 胜出的文档注册，
                              文档在 startup() 时（重复）构建)
    ```

=== "心智模型 — 之后"

    ```
    你运行的任意节点（单个 @service 或 @module）
            │
            ▼
    _cf_collect_routes()  →  list[ResolvedRoute]   (整棵子树，前缀已拼接完成)
            │
            ▼
    _cf_assemble()  →  Assembled(router, openapi)   (记忆化 — 最多执行一次)
            │
            ├─► 一张 Starlette 路由表
            └─► 一份 OpenAPI 文档 + /docs、/redoc、/openapi.json
    ```

核心思想是：**独立运行 == 由 module 装配**。单独运行的 service 与被组合进 module 的同一个
service 会提供完全相同的路径——唯一的区别只是 `_cf_collect_routes()` 收集的子树范围不同。装配逻辑
只有一处，首次访问时记忆化，因此无论你访问多少次 `asgi_app` 或调用多少次 `openapi()`，每个节点最多
只会组装一次。

由此带来两点变化：

- **`ServiceBase.openapi()`** 是新增的公开方法——随时调用（即便服务尚未真正运行）即可获得当前子树
  记忆化后的 OpenAPI 字典。
- **路径冲突现在是真正的报错。** 如果组合树中任意两条路由解析出相同的 `(method, full_path)`，
  组装时会抛出 `ValueError`，而不是静默地保留其中一个。

!!! info "已删除的机制 — 不要再找这些"
    `_collect_routes`、`_route_handler`、`_cf_get_root_routes`、`_cf_collect_route_infos`、
    `_cf_generate_openapi`、`get_mount_path`、"首个 router 胜出" 的文档注册，以及挂载至
    `/{ServiceName}` 的行为，均已删除。如果在旧文档或分支中看到这些引用，请视为过时信息。

## 修复的请求处理缺陷

本轮共修复了 5 个请求处理相关的缺陷：

- **OpenAPI schema 缓存泄漏** — schema 注册表由进程级全局变量改为「每次生成」的局部变量，同一进程
  内重复生成 OpenAPI 文档不再产生悬空的 `$ref`。
- **path 参数与请求体同时存在** — 请求处理现在全程按**参数名**绑定 kwargs；`PUT /x/{id}` 携带
  请求体时不再返回 500。
- **缺失必填 query 参数** — 现在正确返回 **422**（此前是 500）。
- **bool 型 query 参数** — `1/true/yes/on`（大小写无关）→ `True`，`0/false/no/off` → `False`，
  无法识别的值 → 422（此前只认字面量 `true`）。
- **元组返回值** — `(body, status_code)` 现在能正确设置 HTTP 状态码（此前该元组被字符串化，
  始终返回 `200`）。

## 迁移指南

!!! warning "迁移：仅支持显式前缀（D4）"
    **行为变更。** 不再有 `/{ServiceName}` 自动命名空间。如果某个 service 的 `Router` 没有设置
    `prefix`，它现在会直接挂载在裸路径上，而不是 `/{ServiceName}/...`。

    **如果你的 service 依赖隐式挂载：**

    ```python
    # 之前（隐式 /{ServiceName} 命名空间 — 现已不再生效）
    @service()
    class Users(ServiceBase):
        router = Router()  # 曾经可通过 /Users/... 访问

        @router.get("/{user_id}")
        async def get_user(self, user_id: int): ...
    ```

    ```python
    # 之后 — 补上显式前缀以复现旧路径
    @service()
    class Users(ServiceBase):
        router = Router(prefix="/users")

        @router.get("/{user_id}")
        async def get_user(self, user_id: int): ...
    ```

    **迁移清单：**

    1. 搜索代码中未设置 `prefix=` 的 `Router()`（或只带 `tags=...` 而无 prefix 的写法）。
    2. 为每个需要命名空间的 service 补上显式 `prefix=`。
    3. 运行一次应用——组合树中任意 `(method, full_path)` 冲突都会在组装阶段抛出 `ValueError`，
       因此冲突会立即暴露，而不是静默地遮盖某条路由。

    完整说明与更多示例见[挂载 Router](web.md#mount-router)。

## 版本策略

只要**核心设计理念不变**，Canary Framework 就会持续留在 **`0.5.x`** 版本线：

- service 是最小单元；
- module 组合 service 且 module *即是* service；
- 基于类型注解的依赖注入；
- 装饰器驱动的 API。

在此策略下，新特性与修复——包括本页提到的全部内容——都会以 `0.5.x` 发布。内部重构或行为收敛
（例如上文的各项修复）本身**不会**推进版本线；只有底层设计理念发生根本改变时，版本线才会前进。
换句话说：**只要你构建在当前模型之上，`0.5.x` 就是你应该停留的版本线**，它会持续获得修复与改进。

完整版本历史与版本策略的原始表述见
[CHANGELOG](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)。
