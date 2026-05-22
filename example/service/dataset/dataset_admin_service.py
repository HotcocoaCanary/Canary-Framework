import logging

from cf import service, on_init, on_start, on_end, Context

from service.db.db_service import DBService
from service.user.user_service import UserService
from service.dataset.dataset_service import DataSetService
from service.dataset.dataset_config import DataSetConfig

logger = logging.getLogger(__name__)


@service(name="DataSetAdminService", config=DataSetConfig,
         deps=[DBService, UserService, DataSetService])
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
        ds = self.data_set_service.get_dataset(1)
        self.db_service.execute("UPSERT cache ...")
