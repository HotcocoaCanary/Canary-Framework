"""Build stable OpenAPI component schemas and references."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from typing import cast

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from canary_framework.common import RouteCompilationError

_INVALID = re.compile(r"[^a-zA-Z0-9._-]+")


def is_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _name(value: str) -> str:
    return _INVALID.sub("_", value).strip("_") or "Schema"


def _rewrite(value: object, refs: dict[str, str]) -> None:
    if isinstance(value, dict):
        if (ref := value.get("$ref")) in refs:
            value["$ref"] = refs[ref]
        for nested in value.values():
            _rewrite(nested, refs)
    elif isinstance(value, list):
        for nested in value:
            _rewrite(nested, refs)


class SchemaRegistry:
    """Assign stable names and schemas to Pydantic models."""

    def __init__(self, models: Iterable[type]) -> None:
        self._models = tuple(dict.fromkeys(models))
        short = {model: _name(model.__name__) for model in self._models}
        counts = Counter(short.values())
        self._names = {
            model: short[model]
            if counts[short[model]] == 1
            else _name(f"{model.__module__}.{model.__qualname__}")
            for model in self._models
        }
        seen: dict[str, type] = {}
        for model, name in self._names.items():
            if (previous := seen.get(name)) is not None and previous is not model:
                raise RouteCompilationError(f"duplicate OpenAPI schema name {name}")
            seen[name] = model
        self.schemas = self._build()

    def _build(self) -> dict[str, object]:
        if not self._models:
            return {}
        roots, document = models_json_schema(
            [(cast("type[BaseModel]", model), "validation") for model in self._models],
            ref_template="#/components/schemas/{model}",
        )
        definitions = cast("dict[str, object]", document.get("$defs", {}))
        names = {
            model: cast(str, roots[(cast("type[BaseModel]", model), "validation")]["$ref"]).rsplit(
                "/", 1
            )[-1]
            for model in self._models
        }
        refs = {
            f"#/components/schemas/{names[model]}": f"#/components/schemas/{self._names[model]}"
            for model in self._models
        }
        result: dict[str, object] = {}
        for model, name in names.items():
            schema = deepcopy(definitions[name])
            _rewrite(schema, refs)
            result[self._names[model]] = schema
        return result

    def reference(self, model: type) -> dict[str, object]:
        """Return the component reference for a registered model."""
        return {"$ref": f"#/components/schemas/{self._names[model]}"}


__all__ = ["SchemaRegistry", "is_model"]
