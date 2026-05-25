# 完整示例：配置 + 依赖注入 + 生命周期 + Web 路由
import asyncio
import logging

from service.dataset.dataset_admin_service import DataSetAdminService
from service.dataset.dataset_service import DataSetService
from service.db.db_service import DBService
from service.user.user_service import UserService

from canary_framework import Context, config, module, on_end, on_init, on_start
from canary_framework.web.fastapi import WebCanary, get, web

logger = logging.getLogger(__name__)


# 可选：为根模块声明配置（按前缀区分用途）
@config
class AppConfig:
    uvicorn_host: str = "0.0.0.0"  # uvicorn_server: host
    uvicorn_port: int = 8000  # uvicorn_server: port
    fastapi_title: str = "My App"  # FastAPI: title
    fastapi_version: str = "1.0.0"  # FastAPI: version
    # 无前缀 = 业务配置


@web()
@module(
    name="AppModule",
    config=AppConfig,  # 可选：声明配置后，WebCanary 从此读取 host/port
    services=[
        DBService,
        UserService,
        DataSetService,
        DataSetAdminService,
    ],
)
class AppModule:
    # 可选：生命周期钩子 —— 全部可选
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        logger.info("AppModule started")

    @on_end
    def end(self):
        logger.info("AppModule stopped")

    # 可选：直接在模块上定义 HTTP 端点
    @get("/health")
    async def health(self):
        return {"status": "ok"}


if __name__ == "__main__":

    async def main():
        app = WebCanary(AppModule)
        await app.init()
        await app.start()

    asyncio.run(main())
