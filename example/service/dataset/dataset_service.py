import logging

from canary_framework import Context, on_end, on_init, on_start, service
from canary_framework.web.fastapi import web
from service.dataset.dataset_config import DataSetConfig
from service.dataset.dataset_router import DataSetRouter
from service.db.db_service import DBService
from service.user.user_service import UserService

logger = logging.getLogger(__name__)


@web(routers=[DataSetRouter])
@service(name="DataSetService", config=DataSetConfig, deps=[DBService, UserService])
class DataSetService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        logger.info("DataSetService started")

    @on_end
    def end(self):
        logger.info("DataSetService stopped")

    def get_dataset(self, dataset_id: int):
        user = self.user_service.query_user(dataset_id)
        data = self.db_service.execute(f"SELECT * FROM datasets WHERE id={dataset_id}")
        return {"user": user, "data": data}
