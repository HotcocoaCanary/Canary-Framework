"""HTTP route decorators — mark methods as request handlers.

路由装饰器：把 ``@cocoa`` 单元的方法标记为某个 HTTP 方法 + 路径的处理器。仿照
``core/decorator/decorators.py``——只 ``setattr`` 打标记、不改造类，因此方法仍是普通
方法，可以正常继承 / 混入。

标记里带的东西分两类：**影响响应的**（``status_code``）与**只影响文档的**
（``tags`` / ``summary`` / ``deprecated``）。两类都在装配期读一次就固定下来，请求期不碰。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from canary_framework.common.markers import ROUTE_ATTR
from canary_framework.web.infra.checks import require_annotated_sources, require_async

_T = TypeVar("_T", bound=Callable[..., object])

# 这两个状态码按 HTTP 规范不能带响应体，框架据此发一个空响应而不是 JSON 的 "null"。
NO_BODY_STATUSES = frozenset({204, 304})


@dataclass(frozen=True, slots=True)
class RouteMark:
    """What a route decorator wrote down. Read once at assembly, never at request time.

    路由装饰器写下的全部内容，装配期读一次。

    :param method: HTTP 方法，已转大写。
    :param path: 路由自身的路径（不含单元的 ``prefix``），已补上前导斜杠。
    :param status_code: 成功时的状态码。handler 自己造 ``Response`` 时以它为准，这里
        只管"没自己造响应"的那条路。
    :param tags: OpenAPI 分组标签；单元级的 ``tags`` 会拼在前面。
    :param summary: 一句话摘要；不给就用方法名。更长的说明直接写 docstring。
    :param deprecated: 在文档里标记为废弃。
    """

    method: str
    path: str
    status_code: int = 200
    tags: tuple[str, ...] = ()
    summary: str | None = None
    deprecated: bool = False


def route(
    method: str,
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """Mark *fn* as the handler for ``method path``.

    把方法标记为 ``method path`` 的处理器。``method`` 大小写不敏感，``path`` 若缺前缀
    斜杠会自动补齐。

    两条装配期检查在这里把关：handler 必须是 ``async def``（同步函数会阻塞整个进程），
    参数的来源标记必须写在 ``Annotated`` 里（写成默认值会让那个位置表示两件事）。
    """
    method_ = method.upper()
    path_ = path if path.startswith("/") else "/" + path

    def mark(fn: _T) -> _T:
        subject = f"the handler for '{method_} {path_}'"
        require_async(fn, subject)
        require_annotated_sources(fn, subject)
        setattr(
            fn,
            ROUTE_ATTR,
            RouteMark(
                method=method_,
                path=path_,
                status_code=status_code,
                tags=tuple(tags),
                summary=summary,
                deprecated=deprecated,
            ),
        )
        return fn

    return mark


def get(
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """``GET path``."""
    return route(
        "GET", path, status_code=status_code, tags=tags, summary=summary, deprecated=deprecated
    )


def post(
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """``POST path``. 新建资源惯例上用 ``status_code=201``。"""
    return route(
        "POST", path, status_code=status_code, tags=tags, summary=summary, deprecated=deprecated
    )


def put(
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """``PUT path``."""
    return route(
        "PUT", path, status_code=status_code, tags=tags, summary=summary, deprecated=deprecated
    )


def patch(
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """``PATCH path``."""
    return route(
        "PATCH", path, status_code=status_code, tags=tags, summary=summary, deprecated=deprecated
    )


def delete(
    path: str,
    *,
    status_code: int = 200,
    tags: Sequence[str] = (),
    summary: str | None = None,
    deprecated: bool = False,
) -> Callable[[_T], _T]:
    """``DELETE path``. 不返回内容时惯例上用 ``status_code=204``。"""
    return route(
        "DELETE", path, status_code=status_code, tags=tags, summary=summary, deprecated=deprecated
    )
