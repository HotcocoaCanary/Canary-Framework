"""OpenAPI 3.0.3 compilation from validated routes.

每次编译都创建独立的 schema 注册表，并在生成引用前扫描所有可达模型。
Each compilation owns an isolated schema registry and pre-scans every reachable
model before emitting references.
"""

from __future__ import annotations

import re
import warnings
from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from datetime import date, datetime
from datetime import time as _time
from enum import Enum
from typing import Any, Literal, cast, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic.json_schema import models_json_schema

from canary_framework.common import CanaryConfig, RouteCompilationError, unwrap_optional
from canary_framework.engine.validation import ValidatedRoute

_TYPE_MAP: dict[type, str] = {
    int: "integer",
    str: "string",
    bool: "boolean",
    float: "number",
}
_TYPE_FORMAT_MAP: dict[type, str] = {
    datetime: "date-time",
    date: "date",
    _time: "time",
    UUID: "uuid",
    bytes: "byte",
}
_INVALID_COMPONENT_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def _is_model(value: Any) -> bool:
    """Return whether a value is an exact Pydantic model class."""
    return isinstance(value, type) and issubclass(value, BaseModel)


def _sanitize_schema_name(value: str) -> str:
    """Convert a model name to an OpenAPI-safe, deterministic component key."""
    sanitized = _INVALID_COMPONENT_CHARS.sub("_", value).strip("_")
    return sanitized or "Schema"


def _rewrite_references(value: object, references: dict[str, str]) -> None:
    """Rewrite Pydantic definition references to registry-selected names."""
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference in references:
            value["$ref"] = references[reference]
        for nested in value.values():
            _rewrite_references(nested, references)
    elif isinstance(value, list):
        for nested in value:
            _rewrite_references(nested, references)


class SchemaRegistry:
    """Compilation-local model identity, component name, and schema registry."""

    def __init__(self, models: Iterable[type]) -> None:
        ordered = tuple(dict.fromkeys(models))
        short_names = {model: _sanitize_schema_name(model.__name__) for model in ordered}
        short_counts = Counter(short_names.values())
        names = {
            model: (
                short_names[model]
                if short_counts[short_names[model]] == 1
                else _sanitize_schema_name(f"{model.__module__}.{model.__qualname__}")
            )
            for model in ordered
        }
        reverse: dict[str, type] = {}
        for model, name in names.items():
            previous = reverse.get(name)
            if previous is not None and previous is not model:
                raise RouteCompilationError(f"duplicate OpenAPI schema name {name}")
            reverse[name] = model

        self._models = ordered
        self._names = names
        self.schemas = self._build_schemas()

    def _build_schemas(self) -> dict[str, object]:
        """Generate all components together, then rewrite every flattened ref."""
        if not self._models:
            return {}
        roots, document = models_json_schema(
            [(cast("type[BaseModel]", model), "validation") for model in self._models],
            ref_template="#/components/schemas/{model}",
        )
        definitions = cast("dict[str, object]", document.get("$defs", {}))
        references: dict[str, str] = {}
        definition_names: dict[type, str] = {}
        for model in self._models:
            root = cast("dict[str, object]", roots[(cast("type[BaseModel]", model), "validation")])
            old_reference = cast(str, root["$ref"])
            definition_names[model] = old_reference.rsplit("/", 1)[-1]
            references[old_reference] = f"#/components/schemas/{self._names[model]}"

        schemas: dict[str, object] = {}
        for model in self._models:
            definition_name = definition_names[model]
            schema = deepcopy(definitions[definition_name])
            _rewrite_references(schema, references)
            schemas[self._names[model]] = schema
        return schemas

    def reference(self, model: type) -> dict[str, object]:
        """Return a component reference for an exact registered model type."""
        return {"$ref": f"#/components/schemas/{self._names[model]}"}


class OpenAPICompiler:
    """Compile one OpenAPI document exclusively from validated routes."""

    def compile(
        self,
        routes: tuple[ValidatedRoute, ...],
        *,
        config: CanaryConfig,
    ) -> dict[str, object]:
        """Compile routes in declaration order with an isolated schema registry."""
        if not routes:
            return {}

        registry = SchemaRegistry(self._collect_models(routes))
        paths: dict[str, object] = {}
        for validated in routes:
            path_item = cast(
                "dict[str, object]",
                paths.setdefault(validated.analysis.starlette_path, {}),
            )
            path_item[validated.route.method.lower()] = self._operation(validated, registry)

        components: dict[str, object] = {"schemas": registry.schemas}
        if config.openapi_security_schemes:
            components["securitySchemes"] = deepcopy(config.openapi_security_schemes)
        document: dict[str, object] = {
            "openapi": "3.0.3",
            "info": self._info(config),
            "paths": paths,
            "components": components,
        }
        if config.openapi_servers:
            document["servers"] = deepcopy(config.openapi_servers)
        return document

    def _collect_models(self, routes: tuple[ValidatedRoute, ...]) -> tuple[type, ...]:
        """Pre-scan direct and nested Pydantic models in declaration order."""
        models: list[type] = []
        seen: set[type] = set()

        def visit(annotation: Any) -> None:
            if _is_model(annotation):
                model = cast(type, annotation)
                if model in seen:
                    return
                seen.add(model)
                models.append(model)
                for field in cast("type[BaseModel]", model).model_fields.values():
                    visit(field.annotation)
                return
            for argument in get_args(annotation):
                if argument is not type(None):
                    visit(argument)

        for validated in routes:
            spec = validated.route.spec
            visit(validated.analysis.request_model)
            visit(spec.response_model)
            for response in spec.responses.values():
                visit(response.model)
        return tuple(models)

    def _info(self, config: CanaryConfig) -> dict[str, object]:
        """Build document metadata from the runtime root configuration only."""
        info: dict[str, object] = {
            "title": config.openapi_title,
            "version": config.openapi_version,
        }
        if config.openapi_description:
            info["description"] = config.openapi_description
        return info

    def _operation(
        self,
        validated: ValidatedRoute,
        registry: SchemaRegistry,
    ) -> dict[str, object]:
        """Compile one validated route operation without re-analyzing it."""
        route = validated.route
        spec = route.spec
        operation: dict[str, object] = {"operationId": validated.operation_id}
        if route.tags:
            operation["tags"] = list(route.tags)
        if spec.summary:
            operation["summary"] = spec.summary
        if spec.description:
            operation["description"] = spec.description
        if spec.deprecated:
            operation["deprecated"] = True
        if route.security:
            operation["security"] = [{name: [] for name in route.security}]

        parameters = self._parameters(validated)
        if parameters:
            operation["parameters"] = parameters

        if validated.analysis.request_model is not None:
            model = validated.analysis.request_model
            operation["requestBody"] = {
                "description": getattr(model, "__doc__", "") or "",
                "content": {"application/json": {"schema": self._model_schema(model, registry)}},
            }

        operation["responses"] = self._responses(validated, registry)
        return operation

    def _parameters(self, validated: ValidatedRoute) -> list[dict[str, object]]:
        """Build path and query parameters from the retained route analysis."""
        analysis = validated.analysis
        parameters: list[dict[str, object]] = []
        for name in analysis.path_params:
            parameter = analysis.parameters[name]
            parameters.append(
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "schema": _build_parameter_schema(
                        parameter.annotation,
                        parameter.field_info,
                    ),
                }
            )
        for name in analysis.query_params:
            parameter = analysis.parameters[name]
            parameters.append(
                {
                    "name": name,
                    "in": "query",
                    "required": not parameter.has_default,
                    "schema": _build_parameter_schema(
                        parameter.annotation,
                        parameter.field_info,
                    ),
                }
            )
        return parameters

    def _responses(
        self,
        validated: ValidatedRoute,
        registry: SchemaRegistry,
    ) -> dict[str, object]:
        """Build the effective response and overlay explicit response declarations."""
        spec = validated.route.spec
        status = str(spec.status_code)
        successful: dict[str, object] = {"description": "Successful Response"}
        if spec.response_model is not None:
            successful["content"] = {
                "application/json": {"schema": self._model_schema(spec.response_model, registry)}
            }
        responses: dict[str, object] = {status: successful}

        for response_status, response_spec in spec.responses.items():
            key = str(response_status)
            existing = responses.get(key)
            response = (
                dict(cast("dict[str, object]", existing)) if isinstance(existing, dict) else {}
            )
            response["description"] = response_spec.description
            if response_spec.model is not None:
                response["content"] = {
                    "application/json": {
                        "schema": self._model_schema(response_spec.model, registry)
                    }
                }
            responses[key] = response
        return responses

    def _model_schema(self, annotation: Any, registry: SchemaRegistry) -> dict[str, object]:
        """Build component refs or retained inline container schemas."""
        origin = get_origin(annotation)
        if origin is list:
            arguments = get_args(annotation)
            items = self._model_schema(arguments[0], registry) if arguments else {}
            return {"type": "array", "items": items}
        if origin is dict:
            return {"type": "object"}
        if _is_model(annotation):
            return registry.reference(cast(type, annotation))
        return {}


def _enum_values(annotation: Any) -> list[object] | None:
    """Extract declaration-order values from Literal or Enum annotations."""
    origin = get_origin(annotation)
    if origin is Literal:
        return list(get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [member.value for member in annotation]
    return None


def _build_parameter_schema(
    annotation: Any,
    field_info: FieldInfo | None = None,
) -> dict[str, object]:
    """Build a scalar OpenAPI schema while retaining Pydantic field metadata."""
    schema: dict[str, object] = {}
    annotation, nullable = unwrap_optional(annotation)
    if nullable:
        schema["nullable"] = True

    enum_values = _enum_values(annotation)
    if enum_values is not None:
        if all(isinstance(value, bool) for value in enum_values):
            schema["type"] = "boolean"
        elif all(isinstance(value, int) for value in enum_values):
            schema["type"] = "integer"
        elif all(isinstance(value, float) for value in enum_values):
            schema["type"] = "number"
        else:
            schema["type"] = "string"
        schema["enum"] = enum_values
    elif annotation in _TYPE_MAP:
        schema["type"] = _TYPE_MAP[annotation]
    elif annotation in _TYPE_FORMAT_MAP:
        schema["type"] = "string"
        schema["format"] = _TYPE_FORMAT_MAP[annotation]
    else:
        warnings.warn(
            f"Unknown parameter type '{annotation}' — defaulting to 'string' in OpenAPI schema.",
            stacklevel=3,
        )
        schema["type"] = "string"

    if field_info is not None:
        _apply_field_metadata(schema, field_info)
        _apply_field_constraints(schema, field_info)
    return schema


def _apply_field_metadata(schema: dict[str, object], field_info: FieldInfo) -> None:
    """Copy supported Pydantic field documentation metadata."""
    if field_info.description:
        schema["description"] = field_info.description
    if field_info.title:
        schema["title"] = field_info.title
    if field_info.deprecated:
        schema["deprecated"] = True
    examples = field_info.examples
    if isinstance(examples, list) and examples:
        schema["example"] = examples[0]


def _apply_field_constraints(schema: dict[str, object], field_info: FieldInfo) -> None:
    """Copy Pydantic v2 constraints stored on FieldInfo metadata values."""
    mappings = (
        ("min_length", "minLength"),
        ("max_length", "maxLength"),
        ("pattern", "pattern"),
        ("ge", "minimum"),
        ("gt", "exclusiveMinimum"),
        ("le", "maximum"),
        ("lt", "exclusiveMaximum"),
        ("multiple_of", "multipleOf"),
    )
    for metadata in field_info.metadata:
        for attribute, key in mappings:
            if hasattr(metadata, attribute):
                schema[key] = getattr(metadata, attribute)


__all__ = ["OpenAPICompiler"]
