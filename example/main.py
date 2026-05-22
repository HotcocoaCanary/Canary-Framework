from cf import module, on_init, on_start, on_end, ModuleContext, Canary
from cf.web.fastapi import web, get, WebCanary

from service.db.db_service       import DBService
from service.user.user_service   import UserService
from service.dataset.dataset_service        import DataSetService
from service.dataset.dataset_admin_service  import DataSetAdminService

import logging
logger = logging.getLogger(__name__)


@web(routers=[])
@module(
    name="AppModule",
    services=[
        DBService,
        UserService,
        DataSetService,
        DataSetAdminService,
    ],
    config_file_path=".env"
)
class AppModule:

    @on_init
    def init(self, ctx: ModuleContext):
        pass

    @on_start
    def start(self):
        logger.info("AppModule started")

    @on_end
    def end(self):
        logger.info("AppModule stopped")

    @get("/health")
    async def health(self):
        return {"status": "ok"}


if __name__ == "__main__":
    WebCanary(AppModule, log_level="debug").start()
