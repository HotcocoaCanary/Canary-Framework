# 016：类级注解解析失败时，`self.config` / `self.log` 被静默跳过

> | 归因 | **框架 100%** |
> |---|---|
> | 可直接开 issue | ✅ 是（**0.9.3 新增能力里最危险的一处**） |
> | 框架侧改动点 | `core/decorator/introspect.py:annotations_of()` 的 `except` 分支 |
> | 复现依赖 | 零业务代码，8 行 |
> | 业务侧责任 | 无 |

- **类型**：框架 bug（P0）
- **影响版本**：canary-framework 0.9.3（新增能力自带）
- **严重性**：高——单元少了它声明的协作者，装配却报告成功，
  错误推迟到第一次**使用**该属性时才以 `AttributeError` 出现
- **发现场景**：场景一（写 0.9.3 的边界测试时），随后确认场景二同样中招

## 根因

```python
def annotations_of(cls: type) -> dict[str, Any]:
    try:
        return get_type_hints(cls)
    except Exception:
        _log.warning("cannot resolve annotations of %s; skipping annotation injection", ...)
        return {}          # ← 声明被整类丢弃
```

docstring 写着「注解解析不该让应用起不来」。但这个取舍是反的：一个单元写下
`config: RepoConfig` 就是在说「没有它我跑不了」。拿不到它的单元**已经**起不来了，
只是要等到第一次访问才知道。

## 最小复现（两种，都很常见）

### 一、类定义在函数作用域里

```python
async def test_something():
    class LocalConfig(Config):
        size: int = 10

    @cocoa
    class UsesLocal:
        config: LocalConfig
        log: logging.Logger

    app = Canary(UsesLocal)
    await app.init()
    await app.start()        # 成功
```

```
WARNING canary.core.introspect: cannot resolve annotations of UsesLocal; skipping annotation injection
app.state == STARTED
hasattr(unit, "config") == False
hasattr(unit, "log")    == False       ← 连无关的 log 也一起丢了
unit.config.size  → AttributeError: 'UsesLocal' object has no attribute 'config'
```

在 `from __future__ import annotations` 之下（本项目每个文件、框架自己每个文件都有）
注解是字符串，`get_type_hints` 只查模块全局，看不见函数局部作用域。
**测试里就地定义一个假配置类**是最自然的写法，而它恰好必然失败。

### 二、`if TYPE_CHECKING:` 导入的名字

```python
from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from canary_framework import cocoa

if TYPE_CHECKING:
    from collections.abc import Sequence

@cocoa
class Unit:
    log: logging.Logger
    cached: Sequence[int]      # 运行时这个名字不存在
```

```
hasattr(app[Unit], "log") == False
```

这里更刺眼：`cached` 跟框架没有半点关系，它只是个普通的类型提示。但因为
`get_type_hints` 是**整类一次性**解析的，一个解析不了的注解会把同一个类上
**所有**声明连坐掉——包括那行完全合法的 `log: logging.Logger`。

`if TYPE_CHECKING:` 是 ruff / mypy 都在推荐的写法（避免循环导入、加快启动），
所以这不是个边角情况。

## 两个二阶影响

1. **它会掩盖别的错误**。写 #015 的回归测试时，我们本想复现「配置类同时是单元」
   的 `InjectionError`，结果因为类定义在测试函数里，注解被跳过，冲突从未发生，
   测试报「DID NOT RAISE」。把类挪到模块级才复现出来。
   一个静默降级的解析器会让它下游的所有检查都变得不可信。
2. **WARNING 在真实项目里基本看不见**。框架自己「不装 handler、不设 format、
   不碰 root」（这是对的），所以在 `logging.basicConfig` 之前发生的、
   或级别设在 INFO 以上的部署里，这条 WARNING 不会出现在任何地方。

## 期望 vs 实际

| 面 | 期望 | 实际 |
|---|---|---|
| 解析失败 | 抛 `InjectionError`，指名是哪个类的哪个注解，装配当场失败 | WARNING + 静默跳过 |
| 失败范围 | 只影响解析不出来的那一个注解 | 整个类的所有注解一起失效 |
| 失败时机 | 装配期 | 第一次访问属性时的 `AttributeError` |

## 修复建议

**第一步：把「整类连坐」降成「逐条降级」。** `get_type_hints` 是全有或全无的，
所以整类失败时退回到逐条求值：

```python
def annotations_of(cls: type) -> dict[str, Any]:
    try:
        return get_type_hints(cls)
    except Exception:
        return _resolve_one_by_one(cls)


def _resolve_one_by_one(cls: type) -> dict[str, Any]:
    """逐条求值：解析得出来的照常用，解析不出来的只跳过它自己。"""
    resolved: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        ns = vars(sys.modules.get(klass.__module__, None)) or {}
        for name, raw in getattr(klass, "__annotations__", {}).items():
            if not isinstance(raw, str):
                resolved[name] = raw
                continue
            try:
                resolved[name] = eval(raw, ns, dict(vars(klass)))  # noqa: S307
            except Exception:
                _log.warning("%s.%s: 注解无法解析，已跳过", cls.__name__, name)
    return resolved
```

这样 `if TYPE_CHECKING` 那一类就救回来了：`log: logging.Logger` 求得出来，
`cached: Sequence[int]` 求不出来，各自独立，那行合法的 `log` 不再被连坐。

函数局部作用域那一类仍然救不回来（求值时那个作用域已经没了），
所以还需要第二步。

**第二步（更重要）：声明与提示要分开。**

- 一个解析不出来的注解，如果它本来也不是 `Logger` / `Config`，跳过完全正确；
- 一个解析不出来的注解，如果框架**无法判断**它是不是声明，那就不能假装无事发生。

一个更彻底的做法是让声明显式化。其中 `config = inject(RepoConfig)` 这一种
把类型从**注解**（字符串，靠求值还原）搬回了**类属性**（真对象引用），
于是它和 `deps=[RepoConfig]` 一样永远解析得出来——函数局部作用域那一类也一并解决，
因为根本不需要求值。代价是要多写一个 `inject(...)`，
换来的是「声明只有两种结果：装上，或者报错」。

至少，在**跳过了一个类的注解**之后，若该类此后被访问到缺失属性，
错误信息里应该带上「该类的注解未能解析，见启动日志」这条线索。

## 本项目为此付出的代价

- 边界测试里所有涉及 `Config` / `Logger` 注解的辅助类都必须提到模块级，
  哪怕它们只服务于一个测试；
- 业务代码里不敢在任何声明了 `log` / `config` 的单元上使用 `if TYPE_CHECKING` 导入。
  这条约束没法靠 review 保证——它不会报错。

## 回归测试

`apps/library/tests/test_framework_boundaries.py::test_a_locally_scoped_annotation_is_silently_dropped`
