"""
路由上下文 —— 传递给 @router 装饰的路由类的上下文对象。

RouterContext 为路由类提供：
    1. 所属服务实例的引用（self.service）
    2. 从 Registry 中解析依赖服务的能力（self.resolve(SomeService)）

当路由类需要调用某个服务的业务方法时，可以通过 RouterContext.resolve()
获取其依赖的服务实例。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cf.core.registry.registry import Registry

# 泛型占位符，用于 resolve 方法的返回值类型标注
T = object


class RouterContext:
    """
    路由上下文 —— 路由类通过它访问框架基础设施。

    属性：
        service:  所属的服务实例（被 @web 装饰的服务/模块实例）
        _registry: 全局注册表（内部使用）

    方法：
        resolve(svc_cls) → 从注册表中获取指定类型的服务实例

    使用示例：
        @router(prefix="/api/users")
        class UserRouter:
            def __init__(self, ctx: RouterContext):
                self.service = ctx.service           # UserService 实例
                self.db = ctx.resolve(DBService)     # DBService 实例

            @get("/{user_id}")
            async def get_user(self, user_id: int):
                return self.db.query("SELECT * FROM users WHERE id=?", user_id)
    """

    def __init__(self, service: object, registry: "Registry") -> None:
        """
        创建 RouterContext。

        参数：
            service:  所属的服务/模块实例
            registry: 全局注册表
        """
        # 所属服务实例（被 @web 装饰的服务/模块实例）
        self.service = service
        # 全局注册表（内部使用）
        self._registry = registry

    def resolve(self, svc_cls: type[T]) -> T:
        """
        从注册表中解析指定类型的服务实例。

        这是路由类获取依赖服务的主要方式，等价于"手动依赖注入"。

        参数：
            svc_cls: 要获取的 @service 或 @module 声明的类

        返回值：
            该服务的实例对象

        使用示例：
            db = ctx.resolve(DBService)
            db.execute("SELECT ...")
        """
        return self._registry.get_instance(svc_cls)  # type: ignore[no-any-return]
