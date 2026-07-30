"""Compile validated routes into an OpenAPI document."""

from __future__ import annotations

import warnings
from copy import deepcopy
from datetime import date, datetime
from datetime import time as _time
from enum import Enum
from typing import Any, Literal, cast, get_args, get_origin
from uuid import UUID

from pydantic.fields import FieldInfo

from canary_framework.common import CanaryConfig, unwrap_optional
from canary_framework.engine.schema import SchemaRegistry, is_model
from canary_framework.engine.validation import ValidatedRoute

_TYPE_MAP = {int: "integer", str: "string", bool: "boolean", float: "number"}
_TYPE_FORMAT_MAP = {datetime: "date-time", date: "date", _time: "time", UUID: "uuid", bytes: "byte"}
_CONSTRAINTS = {
    "min_length": "minLength",
    "max_length": "maxLength",
    "pattern": "pattern",
    "ge": "minimum",
    "gt": "exclusiveMinimum",
    "le": "maximum",
    "lt": "exclusiveMaximum",
    "multiple_of": "multipleOf",
}


class OpenAPICompiler:
    """Compile validated routes with deterministic component schemas."""

    def compile(
        self,
        routes: tuple[ValidatedRoute, ...],
        *,
        config: CanaryConfig,
    ) -> dict[str, object]:
        """Return one OpenAPI document for the validated routes."""
        if not routes:
            return {}

        registry = SchemaRegistry(self._collect_models(routes))
        paths: dict[str, object] = {}
        for validated in routes:
            path = validated.analysis.starlette_path
            path_item = cast("dict[str, object]", paths.setdefault(path, {}))
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
        models: list[type] = []
        seen: set[type] = set()

        def visit(annotation: Any) -> None:
            if is_model(annotation):
                model = cast(type, annotation)
                if model in seen:
                    return
                seen.add(model)
                models.append(model)
                for field in cast("type[Any]", model).model_fields.values():
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
        info: dict[str, object] = {"title": config.openapi_title, "version": config.openapi_version}
        if config.openapi_description:
            info["description"] = config.openapi_description
        return info

    def _operation(
        self,
        validated: ValidatedRoute,
        registry: SchemaRegistry,
    ) -> dict[str, object]:
        route = validated.route
        spec = route.spec
        operation: dict[str, object] = {"operationId": validated.operation_id}
        for key, value in (
            ("tags", list(route.tags)),
            ("summary", spec.summary),
            ("description", spec.description),
            ("deprecated", spec.deprecated),
        ):
            if value:
                operation[key] = value
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
        analysis = validated.analysis
        names = [(name, "path", True) for name in analysis.path_params]
        names += [
            (name, "query", not analysis.parameters[name].has_default)
            for name in analysis.query_params
        ]
        return [
            {
                "name": name,
                "in": location,
                "required": required,
                "schema": _build_parameter_schema(
                    (p := analysis.parameters[name]).annotation, p.field_info
                ),
            }
            for name, location, required in names
        ]

    def _responses(
        self,
        validated: ValidatedRoute,
        registry: SchemaRegistry,
    ) -> dict[str, object]:
        spec = validated.route.spec
        successful: dict[str, object] = {"description": "Successful Response"}
        if spec.response_model is not None:
            successful["content"] = {
                "application/json": {"schema": self._model_schema(spec.response_model, registry)}
            }
        responses: dict[str, object] = {str(spec.status_code): successful}

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
        origin = get_origin(annotation)
        if origin is list:
            arguments = get_args(annotation)
            items = self._model_schema(arguments[0], registry) if arguments else {}
            return {"type": "array", "items": items}
        if origin is dict:
            return {"type": "object"}
        if is_model(annotation):
            return registry.reference(cast(type, annotation))
        return {}


def _build_parameter_schema(
    annotation: Any,
    field_info: FieldInfo | None = None,
) -> dict[str, object]:
    schema: dict[str, object] = {}
    annotation, nullable = unwrap_optional(annotation)
    if nullable:
        schema["nullable"] = True

    if get_origin(annotation) is Literal:
        enum_values = list(get_args(annotation))
    elif isinstance(annotation, type) and issubclass(annotation, Enum):
        enum_values = [member.value for member in annotation]
    else:
        enum_values = None
    if enum_values is not None:
        value_types = {type(value) for value in enum_values}
        if len(value_types) == 1:
            schema["type"] = _TYPE_MAP.get(next(iter(value_types)), "string")
        schema["enum"] = enum_values
    elif annotation in _TYPE_MAP:
        schema["type"] = _TYPE_MAP[annotation]
    elif annotation in _TYPE_FORMAT_MAP:
        schema.update(type="string", format=_TYPE_FORMAT_MAP[annotation])
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
    for attr in ("description", "title"):
        if value := getattr(field_info, attr):
            schema[attr] = value
    if field_info.deprecated:
        schema["deprecated"] = True
    if field_info.examples:
        schema["example"] = field_info.examples[0]


def _apply_field_constraints(schema: dict[str, object], field_info: FieldInfo) -> None:
    for metadata in field_info.metadata:
        for attribute, key in _CONSTRAINTS.items():
            if hasattr(metadata, attribute):
                schema[key] = getattr(metadata, attribute)
