"""Test helpers: reach a unit in a running graph, and run a graph on test doubles.

测试辅助。只依赖核心的公开 API，不引入任何第三方包，也不依赖某个测试框架::

    async with running(TelemetryDaemon, {Clock: ManualClock()}) as daemon:
        store = unit(daemon, MetricStore)
        ...

- :func:`running` 构造根单元、登记替身、启动整张图，退出时回收。
- :func:`unit` 按类型取回图上的实例，包括测试自己没有声明过依赖的单元。
"""

from canary_framework.test.harness import running
from canary_framework.test.lookup import unit

__all__ = ["running", "unit"]
