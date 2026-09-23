"""Lifecycle flow layer.

运行层：一次运行共享的状态（:mod:`~canary_framework.core.flow.scope`）与依赖图
（:mod:`~canary_framework.core.flow.graph`），以及在图上互为镜像的两条规则——
:func:`~canary_framework.core.flow.enter.enter` 依赖在前地进入一个阶段，
:func:`~canary_framework.core.flow.leave.leave` 本单元在前地离开它。
"""
