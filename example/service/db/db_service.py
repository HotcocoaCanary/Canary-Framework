import logging

from cf import Context, on_end, on_init, on_start, service
from service.db.db_config import DBConfig

logger = logging.getLogger(__name__)


@service(name="DBService", config=DBConfig)
class DBService:
    @on_init
    def init(self, ctx: Context):
        logger.info(f"DBService init with url={ctx.config.url}")

    @on_start
    def start(self):
        logger.info("DBService started")

    @on_end
    def end(self):
        logger.info("DBService stopped")

    def execute(self, sql: str):
        logger.info(f"DBService execute: {sql}")
