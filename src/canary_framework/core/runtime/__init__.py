"""Runtime layer.

运行层：一次运行共享的状态（:mod:`~canary_framework.core.runtime.scope`），以及驱动它的
两条规则——:func:`~canary_framework.core.runtime.advance.advance` 沿依赖递归推进，
:func:`~canary_framework.core.runtime.unwind.unwind` 按台账逆序回收。
"""
