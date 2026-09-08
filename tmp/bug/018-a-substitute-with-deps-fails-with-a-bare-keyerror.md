# 018：替身自己带 `deps` 时，装配崩在框架内部，抛裸 `KeyError`

> | 归因 | **框架 100%** |
> |---|---|
> | 可直接开 issue | ✅ 是（错误质量问题，非功能缺失） |
> | 框架侧改动点 | `runtime/canary.py:_inject()` 取 `self._graph[dep]` 处 |
> | 复现依赖 | 零业务代码，15 行 |
> | 业务侧责任 | 无 |

- **类型**：框架 bug（P2）
- **影响版本**：canary-framework 0.9.3（新增能力自带）
- **发现场景**：场景二，给 `Clock` / `SampleSource` / `AlertSink` 写替身时

## 最小复现

```python
@cocoa
class Collaborator: ...

@cocoa(deps=[Collaborator])
class Real:
    collaborator: Collaborator

@cocoa(deps=[Collaborator])       # 继承 Real 时会把这个标记一起继承
class Stub(Real):
    """继承 Real 只是为了让 mypy 认。"""

@cocoa(deps=[Real])
class Root:
    real: Real

app = Canary(Root, overrides={Real: Stub()})
await app.init()
await app.start()
```

```
KeyError: <class '__main__.Collaborator'>
  File "runtime/canary.py", line 319, in _inject
    claim(to_snake(dep.__name__), f"dependency {dep.__name__}", self._graph[dep])
```

## 为什么会走到这里

两条设计各自都合理，交叉处没接上：

- `build_graph` 对被替换的类型**不展开依赖**（正确：替掉仓储之后不该还去连数据库），
  所以 `Collaborator` 从来没进图；
- `start()` 对图里**每一个**节点调 `_inject`，而 `_inject` 用的是
  `deps_of(type(node))`，也就是**替身自己的** `@cocoa` 标记。

于是替身声明了一个图里不存在的依赖，`self._graph[dep]` 直接 `KeyError`。

## 为什么这不是牵强的写法

发布说明说「替身不必是 `@cocoa`」，读起来像是「随便什么对象都行」。但为了让
`mypy` / `pyright` 在 `overrides={Real: Stub()}` 和 `self.real: Real` 两处都通过，
最自然的做法就是让替身继承被替换的那个类——一继承就把 `@cocoa` 的 deps 标记
（一个普通类属性）带过来了。

我们在场景二里写 `ManualClock(Clock)` 时正好躲过：`Clock` 在重构后没有依赖。
只要 `Clock` 保留任何一个 `deps`，同样的写法就会崩。

## 期望 vs 实际

| 面 | 期望 | 实际 |
|---|---|---|
| 错误类型 | `OverrideError` 或 `InjectionError`（都继承 `CanaryError`） | 裸 `KeyError` |
| 错误信息 | "替身 Stub 声明了依赖 Collaborator，但被替换的类型不展开依赖；替身应自带协作者" | `KeyError: <class 'Collaborator'>` |
| 用户能否 `except CanaryError` 兜住 | 能 | 不能 |

最后一行是重点：框架的错误体系明确承诺「扩展包的错误也继承 `CanaryError`，
这样用户 `except CanaryError` 就能统一捕获」。一个从内部字典漏出来的 `KeyError`
破坏了这个承诺。

## 修复建议

```python
for dep in deps_of(cls):
    if dep not in self._graph:
        raise OverrideError.for_substitute(cls, dep)   # 或一个新的 CanaryError 子类
    claim(to_snake(dep.__name__), f"dependency {dep.__name__}", self._graph[dep])
```

另一种更彻底的选择：**对替身干脆不做依赖注入**，只做配置 / 日志注入，
并在文档里把这条写死（"替身自带协作者"）。目前的行为是"试着注入，注入不到就崩"，
既不是"注入"也不是"不注入"。

顺带：替身的**配置与日志注解**是会被填的（我们的 `HttpSampleSource` /
`WebhookAlertSink` 依赖这个行为），但 `deps` 不会。这两条规则的差异
发布说明没提，建议补一句。

## 回归测试

`apps/telemetry/tests/test_framework_boundaries.py::test_a_substitute_that_declares_deps_dies_with_a_bare_keyerror`
