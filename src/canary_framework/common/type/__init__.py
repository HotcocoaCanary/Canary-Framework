"""Shared domain types — the state-machine base and the core lifecycle state.

框架共享的领域类型：状态机基类与核心生命周期状态。
"""

from enum import Enum


class State(Enum):
    """Base for every state enum in the framework.

    所有状态枚举的基类：``issubclass(MyState, State)`` 可做统一校验。不要给它添加
    成员——它只是一个挂载点，成员由各具体状态枚举定义。
    """


class LifecycleState(State):
    """The states a runtime walks through, one per lifecycle action.

    运行时的状态，和三个动作一一对应：``init()`` 走 ``READY → INITIALIZED``，``start()``
    走 ``INITIALIZED → STARTED``，``stop()`` 走到 ``STOPPED``。每个动作各有一个进行中的
    状态（``*ING``），只可能被并发调用者观察到；非法跳转由 ``LifecycleError`` 拦截。

    起点是 ``READY`` 而不是"什么都还没做"：装配（建图、排序、注入）在
    :class:`~canary_framework.runtime.canary.Canary` 的构造函数里就完成了，所以一个刚
    造出来的运行时**已经可用** —— ``canary[SomeUnit]`` 立刻能取到已注入依赖的实例，
    只是还没有任何钩子跑过。
    """

    READY = "ready"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
