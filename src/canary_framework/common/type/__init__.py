"""Shared domain types — the state-machine base and the core lifecycle state.

框架共享的领域类型：状态机基类与核心生命周期状态。扩展包（web / agent / …）
在 ``common.type`` 里继承 :class:`State` 定义各自的状态枚举。

另含 ASGI 协议类型别名（scope / receive / send），供 runtime 与各扩展在
不 import 具体 web 实现（如 starlette）的前提下共享同一套 ASGI 签名。
"""

from collections.abc import Awaitable, Callable, MutableMapping
from enum import Enum
from typing import Any

# --- ASGI 协议类型别名 -------------------------------------------------
# 与 starlette.types 的 Scope/Receive/Send 保持一致；这里只用标准库，
# 让 runtime 无需反向依赖 web 也能给出精确的 ASGI 签名。
type Scope = MutableMapping[str, Any]
type Message = MutableMapping[str, Any]
type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]


class State(Enum):
    """Base for every string-valued state enum in the framework.

    所有状态枚举的基类。扩展包自定义状态时继承 ``State``，即可用
    ``issubclass(MyState, State)`` 做统一校验。不要给它添加成员——它只是
    一个挂载点，成员由各具体状态枚举定义。
    """


class LifecycleState(State):
    """The eight states a runtime walks through, in order.

    运行时按序经过的八个状态；非法跳转由 ``LifecycleError`` 拦截。
    """

    NEW = "new"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
