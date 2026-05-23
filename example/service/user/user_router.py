from cf import Context
from cf.web.fastapi import router, get, post


@router(prefix="/users")
class UserRouter:

    def __init__(self, ctx: Context):
        self.svc = ctx.service
        self.db  = ctx.service.db_service        # UserService 的 deps 已自动注入

    @get("/{id}")
    async def get_user(self, id: int):
        return await self.svc.query_user(id)

    @post("/")
    async def create_user(self, name: str, email: str):
        return {"name": name, "email": email}
