"""Metadata markers — the contract between declaration and runtime.

元数据标记：装饰器写入、运行时读取的“协议”。集中定义，避免魔法字符串散落各处（DRY）。
"""

_COCOA_ATTR = "__cocoa_deps__"
_ON_INIT = "__on_init__"
_ON_START = "__on_start__"
_ON_STOP = "__on_stop__"
