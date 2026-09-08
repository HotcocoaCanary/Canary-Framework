"""Common — shared types, errors and metadata markers, with no framework logic.

共享层：类型、异常与元数据标记，不掺入框架逻辑。核心包与扩展包（web / agent / …）
都从这里继承基类、共享契约，保证跨包的类型、错误与标记可统一校验、统一捕获。

具体内容见 :mod:`~canary_framework.common.error`、:mod:`~canary_framework.common.type`、
:mod:`~canary_framework.common.markers`。
"""
