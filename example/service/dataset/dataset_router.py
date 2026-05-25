from cf import Context
from cf.web.fastapi import get, router


@router(prefix="/datasets")
class DataSetRouter:
    def __init__(self, ctx: Context):
        self.svc = ctx.service

    @get("/{id}")
    async def get_dataset(self, id: int):
        ds = await self.svc.get_dataset(id)
        return ds
