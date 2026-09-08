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
web      — 可选扩展：@web_cocoa、路由装饰器、请求分发、OpenAPI
```

依赖方向严格无环：`web → runtime → core → common`。每层只认识它的下一层。

包内一律走全路径模块名 —— 各层的 `__init__.py` 只有 docstring，不做转发导出。对外的公开
API 只有两处出口：`canary_framework` 与 `canary_framework.web`。

## 标记，而非魔法

框架通过**标记**沟通 —— 装饰器给类和方法盖上小的字符串常量，运行时再读回它们。所有标记
都收口在 `canary_framework.common.markers`：

| 标记 | 由谁写入 | 由谁读取 |
|---|---|---|
| `COCOA_ATTR` | `@cocoa` | runtime（是否是单元？依赖有哪些？） |
| `ON_INIT` / `ON_START` / `ON_STOP` | 钩子装饰器 | runtime（执行哪些钩子） |
| `ROUTE_ATTR` | `@get` / `@post` / … | web 扩展（方法、路径、状态码、文档元数据） |
| `WEB_ATTR` | `@web_cocoa` | runtime（哪些单元带路由）与 web 扩展（前缀、标题、标签） |

装饰器只 `setattr` 一个标记，从不改造类。这让单元保持普通类，也让自省廉价、无副作用。

MRO 扫描只有一份实现（`core.decorator.introspect.marked_members`）：生命周期钩子和 HTTP
路由读的是同一件事 —— 类上的方法 + 方法上的标记，差别只在载荷。扫描结果按类缓存，因为它
在类创建之后不再变化。

## 两个阶段

1. **声明** — `@cocoa(deps=[...])` 记录依赖；`@on_init`/`@on_start`/`@on_stop` 记录钩子；
   `@get` 记录路由。此时什么都不运行。
2. **解释** — `Canary` 读取标记、建图、排序、注入、驱动生命周期。这个切分让纯图算法可以
   独立测试。

## 引擎

`Canary.__init__` 只校验根。`init()` 建图（每个类型无参构造一次）、跑卡恩拓扑排序、按序
注入依赖并执行 `@on_init`；`start()` 按序执行 `@on_start` 并合并服务入口；`stop()` 逆序
执行 `@on_stop`。排序是确定的，成环以 `CircularDependencyError` 暴露。

图上的实例**全部由框架构造**，没有第二条来源 —— 所以"这个单元是怎么来的"永远只有一个
答案，构造失败与生命周期失败也因此有统一的处置方式。

## 服务：合并成一个应用

`Canary` 是一个 ASGI 应用。`start()` 末尾，它按 `WEB_ATTR` 标记挑出带路由的单元，交给
web 扩展收集并合并成**一个** Starlette 应用，于是整个编排只有一份 `/openapi.json` 与
`/docs`，每个非 `lifespan` 的 scope 都委托给它。

**运行时不做任何路径运算** —— URL 长什么样是 web 的事，运行时只管有哪些单元。`prefix` 是
每个单元的绝对前缀，在 web 扩展的 `collect_routes` 里就拼成完整路径。

合并这一步由 web 扩展完成（`build_serve_app`），`Canary` **延迟** import 它 —— 图上没有
web 单元就不会发生，所以纯 `@cocoa` 编排无需安装 `canary-framework[web]`。

## 请求路径：装配期编译，请求期不反射

web 扩展在**装配期**把每个 handler 的签名编译成一份 `HandlerPlan`：每个形参从哪来、用哪个
校验器、有没有默认值、返回值怎么序列化。请求到来时只是遍历一个元组、按来源取值、跑已经
造好的校验器 —— 不重跑 `get_type_hints`、不重建 `inspect.signature`、不重造 `TypeAdapter`。

同一份计划也供 OpenAPI 生成使用。**分发与文档读的是同一个对象**，所以"文档说这个参数从
查询串来、实际却从请求体读"这种不一致在结构上就不可能发生。

## 设计原则

1. **cocoa 是最小运行单元。** 依赖、状态与生命周期都标记在同一个类上。
2. **装饰器只声明、不改造。** 单元保持普通类。
3. **框架只造空壳。** 一切需要外界输入的事都在生命周期里做 —— 因为只有生命周期里的事情
   才有对应的回收步骤。
4. **生命周期是显式的。** `init()` / `start()` / `stop()` 由你或 ASGI lifespan 调用。
5. **静默失效必须响。** 写了、没报错、也没生效是最难查的问题，所以装配期宁可拒绝。
6. **能力只在使用者自己搭不出来时才由框架提供。** 十行能自己写的东西不该占一个公开入口。
7. **标记集中收口，扩展按需加载。** 一处定义契约，`Canary` 只在真的需要时才 import 扩展。
