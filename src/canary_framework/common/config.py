"""Framework configuration — CanaryConfig base class.

All framework-configurable parameters with sensible defaults and Pydantic
validation.  Users subclass CanaryConfig to customize.

Framework configuration with Pydantic type checking.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CF_CONFIG_MARKER = "__cf_config__"
"""Marker attribute set by @config decorator on config classes."""


class CanaryConfig(BaseModel):
    """Canary Framework configuration base class.

    All parameters have sensible defaults. Override fields in a subclass
    to customize. Extra fields are allowed for user-defined config.
    """

    model_config = {"extra": "allow"}

    # ---- Server ----
    host: str = Field(default="127.0.0.1", description="Server bind address")
    port: int = Field(default=8000, description="Server port", ge=1, le=65535)

    # ---- Logging ----
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Framework log level"
    )

    # ---- OpenAPI Info ----
    openapi_title: str = Field(
        default="Canary Framework API", description="API title for OpenAPI schema"
    )
    openapi_version: str = Field(default="1.0.0", description="API version for OpenAPI schema")
    openapi_description: str = Field(default="", description="API description for OpenAPI schema")
    openapi_servers: list[dict[str, str]] = Field(
        default_factory=list,
        description="OpenAPI servers, e.g. [{'url': 'http://localhost:8000'}]",
    )
    openapi_security_schemes: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="OpenAPI security schemes",
    )

    # ---- Documentation Endpoints ----
    docs_openapi_path: str = Field(
        default="/openapi.json", description="OpenAPI JSON endpoint path"
    )
    docs_swagger_path: str = Field(default="/docs", description="Swagger UI path")
    docs_redoc_path: str = Field(default="/redoc", description="ReDoc path")
    docs_swagger_css_cdn: str = Field(
        default="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        description="Swagger UI CSS CDN URL",
    )
    docs_swagger_js_cdn: str = Field(
        default="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        description="Swagger UI JS CDN URL",
    )
    docs_redoc_cdn: str = Field(
        default="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        description="ReDoc JS CDN URL",
    )


__all__ = ["CF_CONFIG_MARKER", "CanaryConfig"]
