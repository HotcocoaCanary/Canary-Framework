# Router 与 HTTP

继承 `RouterBase` 并应用 `@router`：

```python
from canary_framework import delete, get, patch, post, put, router
from canary_framework.core import RouterBase

@router(prefix="/items", tags=("Items",))
class ItemsRouter(RouterBase):
    @get("/{item_id}")
    async def read(self, item_id: int) -> dict[str, int]:
        return {"id": item_id}
```

## 路径与参数

- Path 模板 `/{item_id}` 绑定同名参数。
- Query 模板 `/search?q={query}&page={page}` 将 query key 绑定到命名参数。
- 支持默认值、`T | None`、Pydantic `Field` 元数据、标量转换与布尔形式。
- 缺失或非法请求值返回 422。

## Body 与响应

`request_model` 选择 Pydantic 请求体参数，`response_model` 控制转换与 schema。处理器可返回 body、Starlette `Response` 或 `(body, status_code)`；声明的 `status_code` 是普通响应默认值。

端点选项包括 `request_model`、`response_model`、`status_code`、`tags`、`summary`、`description`、`deprecated`、`operation_id`、`responses`。

## OpenAPI 与文档

初始化后的运行根从全部后代路由编译 `/openapi.json`、`/docs`、`/redoc`。一个根配置唯一拥有元数据、安全方案、servers 与文档路径。嵌套元数据只贡献 operation 上下文，不能替换根文档元数据。

重复路由、operation ID、文档路径冲突、未知安全方案与不兼容 schema 名会在初始化时失败。
