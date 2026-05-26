# 核心概念

| 概念 | 说明 | 最少声明 | 装饰器 |
|------|------|----------|--------|
| **服务 (Service)** | 最小运行单元 | `@service(name="X")` | `@service` |
| **模块 (Module)** | 服务的组合容器，本身也是服务 | `@module(name="X", services=[...])` | `@module` |
| **上下文 (Context)** | 统一运行时句柄：`get_config` / `get_service` / `resolve` | 框架自动传入 | — |
| **配置 (Config)** | pydantic-settings 子类，自动读 .env | 需要时才声明 | `@config` |
| **生命周期 (Lifecycle)** | `on_init` / `on_start` / `on_end`，通过 `LifecycleHook` 枚举管理 | 需要时才声明 | `@on_init` 等 |

## 类型安全访问

Context 提供了类型安全的访问方法：

```python
@on_init
def init(self, ctx: Context) -> None:
    cfg = ctx.get_config(AppConfig)      # 类型安全，返回 AppConfig
    db  = ctx.resolve(DBService)        # 服务查找
    svc = ctx.get_service(MyService)      # 类型安全，返回 MyService 实例
```



## Context 链

每个服务和模块处于**自己的上下文**中，也存在于**父模块的上下文**中。Context 通过 parent 链向上查找 config 和 resolve。

```
AppModule Context (parent=None)
│  config: AppConfig           # pydantic-settings 自动从 .env 加载
│
├── DBService Context (parent → AppModule)
│   config: AppConfig          # 未声明 config → 沿链找到父模块的
│
├── UserService Context (parent → AppModule)
│   config: UserConfig         # 自己的
│   resolve(DBService) → ✓     # 沿链在父模块 sub_services 中找到
│
└── DataSetService Context (parent → AppModule)
    config: DataSetConfig      # 自己的
    resolve(DBService) → ✓     # 同上
    resolve(UserService) → ✓   # 同上
```
