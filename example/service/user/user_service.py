import logging

from canary_framework import Context, on_end, on_init, on_start, service
from canary_framework.web.fastapi import web
from service.db.db_service import DBService
from service.user.user_config import UserConfig
from service.user.user_router import UserRouter

logger = logging.getLogger(__name__)


@web(routers=[UserRouter])
@service(name="UserService", config=UserConfig, deps=[DBService])
class UserService:
    @on_init
    def init(self, ctx: Context):
        pass

    @on_start
    def start(self):
        logger.info("UserService started")

    @on_end
    def end(self):
        logger.info("UserService stopped")

    def query_user(self, user_id: int):
        return self.db_service.execute(f"SELECT * FROM users WHERE id={user_id}")
