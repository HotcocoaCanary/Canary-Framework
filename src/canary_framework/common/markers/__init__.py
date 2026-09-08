"""Metadata markers — the shared contract written by decorators and read by the runtime.

元数据标记：装饰器写入、运行时读取的“协议”。核心与所有扩展（web / agent / …）的
标记都集中收口在这里，避免魔法字符串散落各处（DRY），也让各包无需互相 import 即可
共享同一份契约。按子系统分组，仅作阅读提示，无运行语义。
"""

# --- core：cocoa 单元与生命周期钩子 ---
COCOA_ATTR = "__cocoa_deps__"
ON_INIT = "__on_init__"
ON_START = "__on_start__"
ON_STOP = "__on_stop__"

# --- web：路由与文档元数据 ---
ROUTE_ATTR = "__canary_route__"
WEB_ATTR = "__canary_web__"
# 实例上暂存的路由条目，由 ``@web_cocoa`` 的启动钩子写入、``Canary`` 合并时读取。
ROUTE_ENTRIES_ATTR = "__canary_route_entries__"
