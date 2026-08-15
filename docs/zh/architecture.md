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
| `SERVE_ATTR` | 单元的 `@on_start` | `Canary`（要委托的服务入口） |
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

## 服务：鸭子类型，而非耦合

`Canary` 是一个 ASGI 应用，却不认识任何具体扩展。`start()` 阶段它扫过各实例，寻找
`SERVE_ATTR` 标记；若有单元暴露了服务入口（web 扩展里就是 Starlette 应用），`Canary` 就
保留它并把每个非 `lifespan` 的 scope 委托给它。

这就是完整的扩展故事：扩展只需（1）使用共享标记，并（2）在 `start()` 阶段把一个应用暴露
到 `SERVE_ATTR` 下。`Canary` 本身从不 import 它。

## 设计原则

1. **cocoa 是最小运行单元。** 依赖、状态与生命周期都标记在同一个类上。
2. **装饰器只声明、不改造。** 单元保持普通类。
3. **生命周期是显式的。** `init()` / `start()` / `stop()` 由你或 ASGI lifespan 调用 ——
   没有隐藏魔法。
4. **所有钩子都可选。** 只有依赖的单元也是完整的。
5. **标记集中收口。** 一处定义契约，魔法字符串不再散落。
6. **运行时对扩展鸭子类型。** `Canary` 通过标记委托服务入口，从不 import 它。
