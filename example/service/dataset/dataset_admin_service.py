import logging

from canary_framework import Context, on_end, on_init, on_start, service
from service.dataset.dataset_config import DataSetConfig
from service.dataset.dataset_service import DataSetService
from service.db.db_service import DBService
from service.user.user_service import UserService

logger = logging.getLogger(__name__)


@service(
    name="DataSetAdminService", config=DataSetConfig, deps=[DBService, UserService, DataSetService]
)
class DataSetAdminService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        logger.info("DataSetAdminService started")

    @on_end
    def end(self):
        logger.info("DataSetAdminService stopped")

    def refresh_cache(self):
        self.data_set_service.get_dataset(1)
        self.db_service.execute("UPSERT cache ...")
