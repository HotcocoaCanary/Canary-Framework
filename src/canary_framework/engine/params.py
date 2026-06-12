"""Route handler parameter resolution utilities.

Provides shared parameter inspection used by both the router and OpenAPI generator.
"""

from __future__ import annotations

import inspect
import warnings
from typing import Any

from pydantic.fields import FieldInfo


def resolve_params(route_fn: Any) -> dict[str, tuple[Any, bool, FieldInfo | None]]:
    """解析路由处理器函数的参数注解、默认值和 Field 信息。

    返回 {param_name: (annotation, has_default, field_info)}，
    "self" 参数被跳过。

    Resolve parameter annotations, defaults, and Field info from a
    route handler function.

    Returns {param_name: (annotation, has_default, field_info)}.
    The "self" parameter is skipped.
    """
    sig = inspect.signature(route_fn)
    try:
        type_hints = inspect.get_annotations(route_fn)
    except Exception as e:
        warnings.warn(
            f"Failed to resolve annotations for '{getattr(route_fn, '__name__', route_fn)}': {e}",
            stacklevel=2,
        )
        type_hints = {}

    result: dict[str, tuple[Any, bool, FieldInfo | None]] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        annotation = type_hints.get(
            name,
            param.annotation if param.annotation is not inspect.Parameter.empty else str,
        )
        has_default = param.default is not inspect.Parameter.empty
        field_info: FieldInfo | None = None
        if has_default and isinstance(param.default, FieldInfo):
            field_info = param.default
        result[name] = (annotation, has_default, field_info)
    return result


__all__ = ["resolve_params"]
