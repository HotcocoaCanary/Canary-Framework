# 配置

## 最小写法：环境变量直接覆盖默认值

```python
from cf import config

@config
class DBConfig:
    url: str = "postgres://localhost:5432"
    pool_size: int = 10
```

pydantic-settings 自动按优先级读取：**环境变量 > .env 文件 > 默认值**。

`@config` 内置 `env_file=".env"`，无需额外配置：

```bash
# .env 文件
DB_URL=postgres://prod:5432/app
DB_POOL_SIZE=20
```

```python
@on_init
def init(self, ctx: Context):
    ctx.config.url        # → postgres://prod:5432/app
    ctx.config.pool_size  # → 20
```

## 服务器、FastAPI 参数也走配置

根模块的 `@config` 类通过**前缀**区分参数归属：

- `uvicorn_*` → uvicorn.Config / uvicorn.Server
- `fastapi_*` → FastAPI() 构造函数
- 无前缀 → 业务配置（框架不触碰）

```python
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"      # → uvicorn(host="0.0.0.0")
    uvicorn_port: int = 8000            # → uvicorn(port=8000)
    uvicorn_workers: int = 1            # → uvicorn(workers=1)
    fastapi_title: str = "My API"       # → FastAPI(title="My API")
    fastapi_version: str = "1.0.0"     # → FastAPI(version="1.0.0")
    fastapi_docs_url: str | None = None # → 关闭文档
    db_url: str = "..."                 # 业务配置（无前缀）
```

WebCanary 自动按前缀拆分、去前缀后分发给对应消费者。
