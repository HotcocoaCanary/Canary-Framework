"""Metadata markers — the shared contract written by decorators and read by the runtime.

元数据标记：装饰器写入、运行时读取的“协议”。集中收口在这里，避免魔法字符串散落各处，
也让各模块无需互相 import 即可共享同一份契约。
"""

COCOA_ATTR = "__cocoa_deps__"
ON_INIT = "__on_init__"
ON_START = "__on_start__"
ON_STOP = "__on_stop__"
