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
