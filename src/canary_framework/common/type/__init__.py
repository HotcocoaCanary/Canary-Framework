"""Shared domain types — the state-machine base and the lifecycle state.

框架共享的领域类型：状态机基类与生命周期状态。
"""

from enum import Enum


class State(Enum):
    """Base for every state enum in the framework.

    所有状态枚举的基类，供 ``issubclass(MyState, State)`` 统一校验。它本身不定义成员。
    """


class LifecycleState(State):
    """The states a runtime walks through, one settled state per lifecycle action.

    每个生命周期动作对应一个完成态，并各有一个进行中状态（``*ING``，只可能被并发调用者
    观察到）::

        Canary(...)     -> READY
        await init()    -> INITIALIZING -> INITIALIZED
        await start()   -> STARTING     -> STARTED
        await stop()    -> STOPPING     -> STOPPED

    任一动作失败转入 ``FAILED``。起点是 ``READY``：装配在 ``Canary(...)`` 里已经完成，
    此时 ``canary[SomeUnit]`` 已可取到注入好依赖的实例，只是尚未跑过任何钩子。
    """

    READY = "ready"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
