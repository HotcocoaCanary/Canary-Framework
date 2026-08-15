"""Naming utilities — Python identifiers to HTTP wire names.

命名工具：把 Python 标识符转换成 HTTP 协议里的名字（如请求头）。
"""


def header_name(name: str) -> str:
    """Map a Python identifier to its HTTP header name (``x_token`` → ``x-token``)."""
    return name.replace("_", "-")
