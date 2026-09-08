# 021：`overrides` 与「按类名注入」互相拉扯，默认实现被迫占用抽象的名字

> | 归因 | **框架 60% / 业务 40%** |
> |---|---|
> | 可直接开 issue | ⚠️ 设计讨论，不是缺陷 |
> | 框架侧改动点 | 无明确改动点；可能是文档 + 一个可选的别名机制 |
> | 复现依赖 | 见下 |
> | 业务侧责任 | 命名是我们自己的选择，但可选项被框架限死了 |

- **类型**：设计反馈（P3）
- **影响版本**：canary-framework 0.9.3
- **发现场景**：两个场景，各 2~3 处

## 现象

`deps=[X]` 注入到 `self.<to_snake(X.__name__)>`。`overrides` 换掉的是**实例**，
不是名字，所以属性名永远是**被声明的那个类**的名字：

```python
@cocoa(deps=[LoggingAlertSink])
class AlertDispatcher:
    logging_alert_sink: LoggingAlertSink

    async def dispatch(self, alert):
        await self.logging_alert_sink.deliver(alert)   # 实际可能是 WebhookAlertSink
```

生产环境跑 `overrides={LoggingAlertSink: WebhookAlertSink()}` 之后，
代码里每一处 `self.logging_alert_sink` 都在说谎。

## 这把命名逼到了一个不太好的位置

两条路，都有代价：

**A. 默认实现占用抽象名**

```python
@cocoa
class AlertSink:            # 名字是抽象的，内容是"写日志"这一种具体实现
    async def deliver(self, alert): logger.warning(...)

class WebhookAlertSink(AlertSink): ...
```

`self.alert_sink` 读起来对了，但现在图里那个叫 `AlertSink` 的东西**既是接口也是
默认实现**。想读"日志实现长什么样"，得去看那个叫抽象名字的类。这也是
Python 生态里常见的做法（`logging.Handler` 就不是），但它意味着**默认实现没有名字**。

**B. 声明抽象基类，默认实现单独一个类**

```python
@cocoa
class AlertSink:                       # 只有抽象方法
    async def deliver(self, alert): raise NotImplementedError

class LoggingAlertSink(AlertSink): ...
```

那么图里 `AlertSink` 会被实例化成那个抽象类本身——`build_graph` 做的是 `t()`，
没有"绑定实现"这一步。必须在**每一次** `Canary(...)` 里都写
`overrides={AlertSink: LoggingAlertSink()}`，包括生产路径。
测试里再覆盖一次。等于把 DI 容器最基本的"接口→默认实现"绑定推给了每个调用点。

我们两个场景都选了 A（`Clock` / `SampleSource` / `EmbeddingModel` / `ChatModel`
都是"抽象名 + 默认实现"），并在 docstring 里写明这一点。能用，
但每次新写一个可替换的单元时都要重新做一次这个取舍。

## 建议

不需要引入接口/Provider 那一整套。两个小得多的东西就够：

1. **`deps` 支持别名**，让注入名与类名解耦：

   ```python
   @cocoa(deps={"sink": LoggingAlertSink})
   class AlertDispatcher:
       sink: LoggingAlertSink
   ```

   注意这跟 0.9.3 的注解声明是同一个方向——注解已经能说"我要什么类型"，
   差的只是"我管它叫什么"。

2. 或者**让类级注解也能声明依赖**（现在只能声明 `Logger` 与 `Config`）：

   ```python
   @cocoa
   class AlertDispatcher:
       sink: LoggingAlertSink       # 类型来自注解，名字来自属性名
   ```

   这样 `deps=[...]` 就只剩"我依赖它但不需要引用它"这一种用途，
   而"我要用它"的情形完全由注解表达——名字自然由使用者定。
   顺带解决 #015 的一半：`deps` 与注解不再是两条会打架的通道，而是一条。

第 2 条听起来是 0.9.3 那个方向的自然终点：既然注解已经是声明了，
把它用完整比停在一半更一致。

## 回归测试

无（这是设计反馈，没有可断言的错误行为）。相关的正向测试：
`apps/telemetry/tests/test_framework_boundaries.py::test_a_substitute_gets_its_lifecycle_hooks_run`
