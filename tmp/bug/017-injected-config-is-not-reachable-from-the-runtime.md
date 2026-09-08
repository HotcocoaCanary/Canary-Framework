# 017：运行时构造并共享的配置实例，没有任何入口能取回来

> | 归因 | **框架 100%** |
> |---|---|
> | 可直接开 issue | ✅ 是（能力缺口，非崩溃） |
> | 框架侧改动点 | `runtime/canary.py`：给 `_configs` 加一个只读入口 |
> | 复现依赖 | 零业务代码，5 行 |
> | 业务侧责任 | 无 |

- **类型**：能力缺口（P2）
- **影响版本**：canary-framework 0.9.3
- **发现场景**：两个场景各 3 处测试、1 处生产代码

## 现象

配置实例由运行时构造（`_config_for`）、整图共享、可被 `overrides` 替换——
但它不在依赖图里，所以 `canary[AppConfig]` 抛 `KeyError`：

```python
app = Canary(LibraryApi)
await app.init()
await app.start()
app[AppConfig]
# KeyError: <class 'config.AppConfig'>
```

`Canary` 的全部读入口是 `state / order / instances / __getitem__`，
它们都基于 `_graph`。`_configs` 是另一个字典，没有任何公开访问路径。

## 为什么这不是"你不需要它"

三处真实需求，每一处我们都被迫绕行：

**1. 测试要断言"我配的值确实生效了"**

```python
# 想写
assert jobs["collect"].interval == runtime[AppConfig].collect_interval_seconds
# 只能写：穿过一个恰好声明了配置的单元
assert jobs["collect"].interval == runtime[CollectorDaemon].app_config.collect_interval_seconds
```

第二种写法把测试绑在了一个无关单元的实现细节上——`CollectorDaemon` 哪天不再声明
配置，这行就得改。

**2. 生产入口要先读配置，才知道往 `overrides` 里放什么**

```python
def build() -> Canary:
    settings = AppConfig()          # ← 第一份
    overrides = {}
    if settings.embedding_provider == "openai":
        overrides[EmbeddingModel] = RemoteEmbeddingModel()
    return Canary(LibraryApi, overrides=overrides)
    #                          ↑ 运行时随后自己再构造第二份
```

一个进程里有两份 `AppConfig`。它们的值目前一致（同一份 env / `.env`），
但这是巧合不是保证：`.env` 在这两次构造之间被改写、或某个字段带
`default_factory=lambda: uuid4()`，两份就不同了。要避免，只能把第一份也塞进
`overrides`，即用一个变通去修另一个变通。

**3. 运维快照 / health 端点想报告"当前生效的配置"**

同 1，得穿过某个单元。

## 期望

```python
app.config(AppConfig)     # -> AppConfig，与注入给各单元的是同一个对象
app.configs               # -> Mapping[type, object]，装配摘要里已经有这些信息了
```

`_assembly_summary()` 已经在 DEBUG 里打印替身与依赖，说明运行时并不认为这些是
私有信息，只是没有对外的读法。

顺带一提：加了这个入口之后，第 2 条也能顺势解决——如果 `Canary` 允许在
`init()` 之后、`start()` 之前读到配置，`build()` 就不必自己先构造一份。
不过那会引出「配置在 init 阶段就要可用」的时序问题，
所以更简单的做法是：`overrides` 里显式放入自己构造的那一份，
而框架把「同一个配置类只会存在一个实例」这件事**在文档里写清楚**——
目前发布说明写的是「同一份配置类整图共享一个实例」，
读起来像是承诺了唯一性，实际只覆盖运行时自己构造的那些。

## 回归测试

`apps/telemetry/tests/test_lifecycle.py::test_the_scheduler_registers_both_jobs`（注释处）
`apps/library/app/testing.py::effective_config`（绕行封装在这里）
