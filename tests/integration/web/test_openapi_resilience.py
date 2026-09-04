"""Integration — the OpenAPI document must survive types it cannot describe.

文档生成的失败路径：一个无法生成 schema 的类型不该连累整份文档；Starlette 的路径
转换器也不该泄漏进文档。
"""

from __future__ import annotations

from typing import TextIO

import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from canary_framework import Canary
from canary_framework.web import get, web_cocoa

pytestmark = pytest.mark.integration


def test_an_undescribable_type_degrades_instead_of_crashing_the_doc() -> None:
    """旧版：一个 handler 的类型生成不出 schema → 整份 /openapi.json 500。"""

    @web_cocoa
    class API:
        @get("/stream")
        async def stream(self) -> TextIO:  # pydantic 无法为它生成 schema
            raise NotImplementedError

        @get("/healthy")
        async def healthy(self) -> dict:
            return {"ok": True}

    with TestClient(Canary(API)) as client:
        r = client.get("/openapi.json")

    assert r.status_code == 200
    doc = r.json()
    # 描述不了的那个退化成「未约束」，其余端点照常有文档。
    assert (
        doc["paths"]["/stream"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        == {}
    )
    assert "/healthy" in doc["paths"]


def test_path_converter_does_not_leak_into_the_document() -> None:
    """``{name:path}`` 是 Starlette 的路由语法，OpenAPI 只认 ``{name}``。"""

    @web_cocoa
    class API:
        @get("/files/{name:path}")
        async def download(self, name: str) -> dict:
            return {"name": name}

    with TestClient(Canary(API)) as client:
        doc = client.get("/openapi.json").json()
        served = client.get("/files/a/b/c.txt")

    assert "/files/{name}" in doc["paths"]
    assert "/files/{name:path}" not in doc["paths"]
    assert served.json() == {"name": "a/b/c.txt"}  # 路由行为不受影响


def test_response_returning_handlers_declare_no_json_schema() -> None:
    """handler 自己造响应时，媒体类型由它决定——文档不该硬说成 JSON。"""

    @web_cocoa
    class API:
        @get("/plain")
        async def plain(self) -> PlainTextResponse:
            return PlainTextResponse("hi")

    with TestClient(Canary(API)) as client:
        doc = client.get("/openapi.json").json()

    assert doc["paths"]["/plain"]["get"]["responses"]["200"] == {
        "description": "Successful Response"
    }
