from cf.web.fastapi import router, get, RouterContext


@router(prefix="/datasets")
class DataSetRouter:

    def __init__(self, ctx: RouterContext):
        self.svc = ctx.service

    @get("/{id}")
    async def get_dataset(self, id: int):
        ds = await self.svc.get_dataset(id)
        return ds
