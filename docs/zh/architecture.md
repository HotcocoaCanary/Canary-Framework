# 架构

框架是普通 Python 类之上的一层薄薄的分层。它把**声明**（类上的标记）与**解释**（读取标记
的运行时）分开。

## 分层

```
common   — 共享的类型、异常与元数据标记（不含框架逻辑）
   ▲
core     — 声明层原语：@cocoa、@on_init/@on_start/@on_stop、自省
   ▲
runtime  — 引擎：Canary、建图、拓扑排序
   ▲
web      — 可选扩展：@web_cocoa、路由装饰器、OpenAPI
```

依赖方向严格无环：`web → runtime → core → common`。每层只认识它的下一层。

## 标记，而非魔法

框架通过**标记**沟通 —— 装饰器给类和方法盖上小的字符串常量，运行时再读回它们。所有标记
都收口在 `canary_framework.common.markers`，按子系统分组：

| 标记 | 由谁写入 | 由谁读取 |
|---|---|---|
| `COCOA_ATTR` | `@cocoa` | runtime（是否是单元？依赖有哪些？） |
| `ON_INIT` / `ON_START` / `ON_STOP` | 钩子装饰器 | runtime（执行哪些钩子） |
| `ROUTE_ENTRIES_ATTR` | `@web_cocoa` 的 `@on_start` | `Canary`（待合并的路由条目） |
| `ROUTE_ATTR` / `WEB_ATTR` | `@get`/… 与 `@web_cocoa` | web 扩展 |

装饰器只 `setattr` 一个标记，从不改造类。这让单元保持普通类，也让自省廉价、无副作用。

## 两个阶段

1. **声明** — `@cocoa(deps=[...])` 记录依赖；`@on_init`/`@on_start`/`@on_stop` 记录钩子。
   此时什么都不运行。
2. **解释** — `Canary` 读取标记、建图、排序、驱动生命周期。这个切分让纯图算法可以独立
   测试。

## 引擎

`Canary.__init__` 校验根并构建实例图。`init()` 对 `deps=[...]` 跑卡恩拓扑排序并按序执行
`@on_init`；`start()` 注入依赖后执行 `@on_start`；`stop()` 逆序执行 `@on_stop`。排序是确定
的，成环以 `CircularDependencyError` 暴露。

## 服务：合并成一个应用

`Canary` 是一个 ASGI 应用。`start()` 阶段每个 `@web_cocoa` 单元把自己的路由条目
（`METHOD`、路径、实例、处理器）写到 `ROUTE_ENTRIES_ATTR` 下；`Canary` 把它们收拢成
**一个**应用，于是整个编排只有一份 `/openapi.json` / `/docs` / `/redoc`，每个非
`lifespan` 的 scope 都委托给它。

挂载位置由依赖图决定（`runtime/mounts.py`，纯算法、可独立测试）：从每个根深度优先走依赖
边，逐级拼接 `prefix`，非 web 单元透明跳过。规则只有一条——**实例共享，挂载不共享**：类型
仍是单例，但被两条依赖路径引用就在两处各挂一份。相同的 `(类型, 前缀)` 只走一次，既去重也
避免菱形依赖下的路径爆炸。

合并这一步由 web 扩展完成（`build_serve_app`），`Canary` **延迟** import 它——没有路由条目
就不会发生，所以纯 `@cocoa` 编排无需安装 `canary-framework[web]`。

## 设计原则

1. **cocoa 是最小运行单元。** 依赖、状态与生命周期都标记在同一个类上。
2. **装饰器只声明、不改造。** 单元保持普通类。
3. **生命周期是显式的。** `init()` / `start()` / `stop()` 由你或 ASGI lifespan 调用 ——
   没有隐藏魔法。
4. **所有钩子都可选。** 只有依赖的单元也是完整的。
5. **标记集中收口。** 一处定义契约，魔法字符串不再散落。
6. **扩展按需加载。** 扩展通过共享标记暴露元数据，`Canary` 只在真的需要时才 import 它。
