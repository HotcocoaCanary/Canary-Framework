# Canary Framework

面向普通 Python 类的**依赖注入**与**生命周期**框架。纯标准库，零第三方依赖。

继承 `Canary` 即为一个最小单元：它声明自己依赖谁，也声明自己在各阶段做什么。启动一个
单元，它的依赖按依赖顺序就位；退出时逆序回收。

```python
import asyncio

from canary_framework import Canary, dep, init, start, stop


class Config(Canary):
    @init
    def load(self) -> None:
        self.dsn = "postgresql://localhost/dev"


class Database(Canary):
    config = dep(Config)

    @start
    async def connect(self) -> None:
        print(f"连接 {self.config.dsn}")

    @stop
    async def close(self) -> None:
        print("断开连接")


class UserService(Canary):
    database = dep(Database)


async def main() -> None:
    async with UserService() as service:
        print(service.database.config.dsn)


asyncio.run(main())
```

## 两条规则

整个框架只有两条规则。

**推进**沿依赖递归：一个单元进入某个阶段之前，它的依赖已经完成该阶段。同一个单元的同一个
阶段只运行一次，无论有多少单元依赖它；互不依赖的依赖同时推进。

**回收**按台账线性进行：依赖图不是树，一个单元可能被多个单元依赖，因此回收不能沿依赖
递归，只能按进入顺序逆序执行。

`init` / `start` / `stop` 是这两条规则的三个名字。

## 核心概念

| 名字 | 是什么 |
|---|---|
| `Canary` | 单元基类。继承它即为一个单元，并获得四个生命周期动作。 |
| `dep(Cls)` | 依赖声明。属性名由你决定，与被依赖的类名无关。 |
| `@init` / `@start` / `@stop` | 阶段标记。标注该方法在哪个阶段运行。 |
| `Phase` | 阶段本身。`Phase("migrate")` 即是第四个阶段，无需注册。 |
| `Scope` | 一次运行共享的状态。一个作用域就是一张图。 |

## 不变量

1. **单元一律由框架无参构造。** 需要外界输入的事情发生在生命周期钩子里，因为只有那里的
   事情才有对应的回收步骤。
2. **一个作用域内，每个类型只有一个实例。** 两个各自构造的根是两张互不相干的图。
3. **依赖在 `@init` 之后才可用。** 在 `__init__` 中读取依赖会抛 `LifecycleError`。
4. **全部 `@init` 完成之后，才有任何 `@start` 运行。**
5. **`stop()` 是唯一的回收路径。** 正常结束与失败结束共用，重复调用幂等。

## 安装

```bash
pip install canary-framework
```

需要 Python 3.12 或更高版本。安装不会引入任何第三方包。

## 下一步

- [快速开始](quickstart.md)：十分钟跑通一个完整的例子。
- [单元](canary.md)：`Canary` 基类的四个动作。
- [依赖声明](dependency-injection.md)：`dep()` 与作用域。
- [生命周期](lifecycle.md)：阶段、栅栏、失败与回收。
- [架构](architecture.md)：分层与依赖方向。
- [API 参考](api-reference.md)：全部公开名字。
