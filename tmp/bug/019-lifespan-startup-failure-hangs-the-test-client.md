# 019：lifespan 启动失败后框架 `return` 而不 `raise`，挂起被挪到了 shutdown

> | 归因 | **框架 100%** |
> |---|---|
> | 可直接开 issue | ✅ 是（**0.9.3 修复引入的回归，本轮最严重的问题**） |
> | 框架侧改动点 | `runtime/canary.py:_lifespan()` 的 `except` 分支 |
> | 复现依赖 | 零业务代码，20 行 |
> | 业务侧责任 | 无 |

- **类型**：框架 bug（P0，回归）
- **影响版本**：canary-framework 0.9.3
- **严重性**：高——`TestClient` 会报告一个**根本没启动的应用启动成功了**，
  随后在退出上下文时永久挂起。整个测试套件卡死，没有超时、没有报错。
- **发现场景**：场景一。升级后第一次 `uv run pytest` 就卡住了，
  120s 没有任何输出，需要 `faulthandler` 才定位到。

## 现象

```python
@web_cocoa
class Api:
    @on_start
    async def boom(self) -> None:
        raise RuntimeError("启动失败")

    @get("/ping")
    async def ping(self) -> str:
        return "pong"

with TestClient(Canary(Api)) as client:      # ← 进入成功（!）
    client.get("/ping")                      # RuntimeError: Canary has no serving app...
# ← 退出 with：永久挂起
```

实测输出：

```
ENTER: TestClient 进入成功 —— 但应用其实没启动
REQUEST raised: RuntimeError Canary has no serving app for scope type 'http'
EXIT: 即将退出 with —— 这里会挂住
HUNG
```

## 根因

0.9.3 修掉了「发完 `startup.failed` 还在 `await receive()` 导致进程永久挂起」，
修法是发完就 `return`：

```python
except Exception as exc:
    # 启动失败即宣告 lifespan 结束：服务器不会再发 shutdown，
    # 继续 await receive() 会让调用方（如 TestClient）一直挂着。
    await send({"type": "lifespan.startup.failed", "message": str(exc)})
    return                    # ← 异常被吞掉了
```

注释里点名的正是 `TestClient`，但 `TestClient` 恰恰是被这个修法打中的那个。
Starlette 的 lifespan 客户端这样等：

```python
async def receive():
    message = await self.stream_send.receive()
    if message is None:
        self.task.result()          # ← 靠 lifespan 任务抛异常来传播失败
    return message

message = await receive()
if message["type"] == "lifespan.startup.failed":
    await receive()                 # 期望这里因为 task.result() 而抛出
```

因为 `_lifespan` 是**正常返回**的，`self.task.result()` 返回 `None`，
`receive()` 返回 `None`，`wait_startup` 静静地结束——`__enter__` 成功。
而 lifespan 任务已经退出，它的 `finally` 里那一个 `None` 也被这次 `receive()`
消费掉了。于是 `__exit__` 里的 `wait_shutdown` 永远等不到任何消息。

**挂起没有消失，只是从 `__enter__` 搬到了 `__exit__`。**

## 参照实现

Starlette 自己的 `Router.lifespan` 是发完再抛：

```python
except BaseException:
    exc_text = traceback.format_exc()
    if started:
        await send({"type": "lifespan.shutdown.failed", "message": exc_text})
    else:
        await send({"type": "lifespan.startup.failed", "message": exc_text})
    raise                     # ← 这一行是关键
```

uvicorn 看到 `startup.failed` 就退出进程，所以「抛不抛」它都能工作；
`TestClient` 靠 `task.result()` 拿异常，所以「抛不抛」决定了它是报错还是挂死。
ASGI 规范没规定必须 raise，但生态里的调用方都按 Starlette 的实现来。

## 修复建议

```python
except Exception as exc:
    await send({"type": "lifespan.startup.failed", "message": str(exc)})
    raise
```

一行。`send` 已经发出去了，所以 uvicorn 的行为不变（它已经决定退出）；
`TestClient` 则能在 `__enter__` 处抛出真正的 `RuntimeError("启动失败")`，
这正是使用者想看到的东西。

建议同时给 shutdown 分支补上对称的处理：`stop()` 现在会抛 `ExceptionGroup`
（见发布说明），当前代码是

```python
elif message["type"] == "lifespan.shutdown":
    try:
        await self.stop()
    finally:
        await send({"type": "lifespan.shutdown.complete"})
    return
```

即无论 `stop()` 是否失败都汇报 `shutdown.complete`。关停失败会被完全隐藏——
按同样的逻辑，这里应该发 `lifespan.shutdown.failed` 并把 `ExceptionGroup` 抛出去。

## 建议加一条框架自己的回归测试

框架的测试套件如果用 `httpx.ASGITransport` 或直接驱动 `_lifespan`，
就测不到这条——它只在**完整实现了 lifespan 客户端**的调用方身上暴露。
建议加一个直接用 `starlette.testclient.TestClient` 的用例：

```python
def test_a_startup_failure_reaches_the_caller():
    with pytest.raises(RuntimeError, match="启动失败"):
        with TestClient(Canary(Broken)):
            pass
```

## 本项目为此付出的代价

整个 141 个测试的套件在升级后第一次运行时直接挂死，没有任何输出。
定位过程：`timeout -s ABRT` + `python -X faulthandler` 拿到线程栈，
才看到卡在 `starlette/testclient.py:702 wait_shutdown`。
这对一个内测版来说代价还算可以接受，对一条发布出去的升级路径就不是了。

## 回归测试

`apps/library/tests/test_framework_boundaries.py::test_a_startup_failure_leaves_the_test_client_hanging_on_shutdown`
（该测试在**另一个线程**里驱动 `TestClient` 并 `join(timeout=5)`，
所以它断言挂起而不会自己挂住。框架修好后它会失败，那就是删掉它的信号。）
