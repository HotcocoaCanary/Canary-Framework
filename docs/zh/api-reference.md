# API 参考

## 公共声明

### `service`

```text
service() -> Callable[[type[ServiceBase]], type[ServiceBase]]
```

`service` 没有参数。它校验并标记一个 `ServiceBase` 子类，使其成为生命周期与依赖注入节点。返回值是原类本身，不是包装类。参见[服务](services.md)。

### `config`

```text
config() -> Callable[[type[CanaryConfig]], type[CanaryConfig]]
```

`config` 没有参数。它返回一个类装饰器：要求目标类继承 `CanaryConfig`，将其标记为框架配置类，并原样返回该类，不包装也不实例化。用于其他类时抛出 `TypeError`。Router 与 Module 的 `config=` 参数同样要求 `CanaryConfig` 子类。全部内置字段见[配置](configuration.md)。

### `router`

```text
router(*, prefix: str = "", tags: Sequence[str] = (),
       security: Sequence[str] = (),
       config: type[CanaryConfig] | None = None)
    -> Callable[[type[RouterBase]], type[RouterBase]]
```

- `prefix`：加到该 Router 所有端点前的路径前缀。
- `tags`：所有端点继承的标签，位于祖先 Module 标签之后。
- `security`：追加到继承项后的 OpenAPI 安全方案名，按顺序去重；每个名称都必须存在于运行根配置中。
- `config`：仅当该 Router 是运行根时使用的配置类。组合在 Module 下的 Router 接收 Module 选定的配置。
- 返回值：类装饰器；它校验 `RouterBase` 子类、附加端点元数据，并返回原类。

参见 [Web 与路由](web.md)和[配置](configuration.md)。

### `module`

```text
module(*, children: Sequence[type] = (), prefix: str = "",
       tags: Sequence[str] = (), security: Sequence[str] = (),
       config: type[CanaryConfig] | None = None)
    -> Callable[[type[ModuleBase]], type[ModuleBase]]
```

- `children`：显式组合的已装饰 Service、Router 或 Module 类，保持声明顺序；配置类不能作为 child。
- `prefix`：递归加到所有 Router 后代前的路径前缀。
- `tags`：加在后代端点标签之前的标签。
- `security`：后代继承的安全方案名，按顺序去重。
- `config`：该 Module 作用域选定的配置类。未指定时，嵌套 Module 继承最近祖先 Module 的配置；根 Module 回退到 `CanaryConfig`。
- 返回值：类装饰器；它校验并返回原 `ModuleBase` 子类，使其成为 DI 作用域与可能的运行根。

Module 不能直接声明端点。参见 [Module](modules.md)。

## 端点装饰器

`get`、`post`、`put`、`delete`、`patch` 共享以下签名：

```text
(path: str, *, request_model: type | None = None,
 response_model: type | None = None, status_code: int = 200,
 tags: Sequence[str] = (), summary: str | None = None,
 description: str | None = None, deprecated: bool = False,
 operation_id: str | None = None,
 responses: Mapping[int | str, ResponseSpec] | None = None)
    -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]
```

- `path`：端点局部路径。`/{item_id}` 这样的 path 模板绑定路径参数；`/search?q={query}&page={page}` 这样的 query-template 声明并绑定查询参数，而编译后的 Starlette 路径仍为 `/search`。
- `request_model`：请求体模型；它选择唯一一个未出现在 path/query 模板中的处理器参数。
- `response_model`：仅用于 OpenAPI schema 与文档的响应模型；实际响应体根据处理器返回值序列化。
- `status_code`：声明的成功状态码，默认 `200`。
- `tags`：追加在继承的 Module、Router 标签之后的端点局部标签。
- `summary`：可选 OpenAPI 操作摘要。
- `description`：可选 OpenAPI 操作描述。
- `deprecated`：启用时输出 OpenAPI `deprecated: true` 标记。
- `operation_id`：显式 OpenAPI 操作 ID；默认值为 `RouterClass.handler_name`，重复值会导致路由编译失败。
- `responses`：按整数或字符串状态码索引的附加/覆盖响应文档；每个值为 `ResponseSpec(description, model)`。
- 返回值：记录不可变路由元数据、并原样返回强类型 async 处理器的装饰器，不包装处理器。

运行时状态码优先级明确：返回 Starlette `Response` 时保留其状态；返回 `(body, integer_status)` 时使用 tuple 状态；否则使用 `status_code`。`responses` 只描述状态，不改变运行时状态选择。

## 基类

### `ServiceBase`

- `async init() -> None`：执行结构初始化，然后调用 `on_init()`。
- `async startup() -> None`：启动长生命周期资源，然后调用 `on_startup()`。
- `async shutdown() -> None`：调用 `on_shutdown()` 并停止资源。
- `config -> CanaryConfig | None`：运行根或包含它的 Module 选定的配置。
- `lifecycle_state -> LifecycleState`：当前生命周期状态。

异步扩展点是 `on_init()`、`on_startup()`、`on_shutdown()`。`ServiceBase` 不是 ASGI 应用，也没有路由或 OpenAPI API。

### `RouterBase` 与 `ModuleBase`

两者都继承 Service 生命周期。当作为运行根时，还提供：

- `asgi_app`：初始化后延迟编译并缓存的 ASGI 应用。
- `openapi() -> dict[str, object]`：与该 ASGI 应用对应的缓存 OpenAPI 文档。
- `async __call__(scope, receive, send) -> None`：ASGI HTTP 与 lifespan 入口。

`RouterBase.route_specs` 暴露不可变端点声明；`ModuleBase.direct_children` 按声明顺序暴露已初始化的直接子节点。组合在其他 Module 下的 Router/Module 不是运行根，不能独立服务或提供自己的 OpenAPI 文档。

## 生命周期状态与回滚

状态包括 `CREATED`、`INITIALIZED`、`STARTED`、`STOPPED`、`FAILED`。唯一合法的公共顺序是 `await init()`、`await startup()`、`await shutdown()`。重复某阶段、跳过阶段、从 `FAILED` 调用公共 `shutdown()`，或再次使用已停止节点，都会抛出 `LifecycleStateError`。

初始化或启动失败后，节点保持 `FAILED`。框架会按生命周期逆序，对已经初始化或启动的后代执行私有、幂等回滚，并抑制清理异常，避免覆盖原始错误。回滚不会把失败节点改成 `STOPPED`，也不是公共生命周期方法。参见[生命周期](lifecycle.md)。

## 错误

公共错误包括 `ApplicationNotInitializedError`、`CircularDependencyError`、`ConfigurationError`、`DependencyDirectionError`、`DependencyInjectionError`、`LifecycleHookError`、`LifecycleStateError`、`RouteCompilationError`、`ServiceNotFoundError`，均继承 `CanaryFrameworkError`。
