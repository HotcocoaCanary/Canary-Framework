# 015：配置类同时是 `@cocoa` 单元时，两条声明通道互相冲突，装配被拒

> | 归因 | **框架 90% / 业务 10%** |
> |---|---|
> | 可直接开 issue | ✅ 是（**升级 0.9.3 撞上的第一堵墙**，两个场景各撞 6 处和 8 处） |
> | 框架侧改动点 | `runtime/canary.py:_inject()` 的 `claim()`；或 `common/config` 侧禁止 `@cocoa` 标记 `BaseSettings` 子类 |
> | 复现依赖 | 零业务代码，10 行 |
> | 业务侧责任 | 0.9.2 时把配置写成 `@cocoa` 单元——那在当时是**唯一**的写法 |

- **类型**：破坏性变更缺少迁移路径（P1）
- **影响版本**：canary-framework 0.9.3（0.9.2 无此问题）
- **发现场景**：两个场景**同时**。这是升级过程中遇到的第一个错误，
  在改动任何一行业务逻辑之前就发生了。

## 最小复现

```python
from canary_framework import Canary, Config, cocoa

@cocoa                       # ← 0.9.2 的标准写法
class AppConfig(Config):
    size: int = 1

@cocoa(deps=[AppConfig])     # ← 0.9.2 的标准写法
class Uses:
    app_config: AppConfig    # ← 0.9.2 里这行纯粹是写给 mypy 看的

app = Canary(Uses)
await app.init()
await app.start()
```

```
InjectionError: Uses.app_config is claimed by more than one source:
                dependency AppConfig, annotation AppConfig
```

## 为什么这个组合是 0.9.2 的常规写法，而不是我们写歪了

0.9.2 没有配置注入。`Config` 基类不存在，`deps=[...]` 是把任何东西送进单元的唯一
通道，所以配置只能写成 `@cocoa class AppConfig(BaseSettings)`。而
`app_config: AppConfig` 这行注解在 0.9.2 里**没有任何运行时含义**——它是给类型检查
器看的，框架文档里的示例也这么写。

0.9.3 给注解赋予了运行时含义，于是这两行从「一次声明 + 一条类型提示」变成了
「两次声明」。冲突检测本身是对的（见 #007，我们当初就要求过它），但它现在打击的是
**上一版的正确写法**，且：

1. 报错信息说了"被两个来源认领"，没说**该删哪一个**；
2. 两条通道给的其实是**不同的对象**——`deps` 给图里的单例，注解给
   `self._configs[AppConfig]` 另外构造的一份。所以即使不报错，也会静默拿到两份配置；
3. 每一个声明了配置的单元都会撞一次。场景一 6 处、场景二 8 处，
   全都要改，且必须一次性改完才能启动。

## 我们的修法

1. `AppConfig` 去掉 `@cocoa`，基类从 `BaseSettings` 换成 `canary_framework.Config`；
2. 把 `AppConfig` 从所有 `deps=[...]` 里删掉；
3. `app_config: AppConfig` 注解原样保留——它现在是真声明了。

代价是每个应用一次性改 6~8 处，改完之后确实更干净：配置不再占据拓扑序里的一个节点。
但这条路径靠的是读框架源码推出来的，发布说明里没有。

## 修复建议

按优先级：

1. **在 `@cocoa` 处就拒绝**：`cocoa()` 遇到 `BaseSettings` 子类直接抛
   `CanaryError("配置类不要标记 @cocoa —— 写成类级注解即可")`。错误离现场最近，
   一次就说清楚该怎么改。
2. 或者**让两条通道合流**：`claim()` 发现两个来源指向同一个类型时不算冲突，
   统一解析为配置实例。代价是"同一个类型既是单元又是配置"这件事被默许了，
   不如第 1 条干净。
3. 无论选哪条，`InjectionError` 的信息里应该带上**建议动作**，
   而不只是陈述冲突。

## 回归测试

`apps/library/tests/test_framework_boundaries.py::test_a_settings_class_may_not_also_be_a_unit`
