"""
WebCanary 引擎 —— 为 Canary 框架提供 FastAPI + Uvicorn 集成。

WebCanary 是 Canary 的 Web 层包装器，在继承了 Canary 的完整生命周期管理能力上，
额外提供了：
    1. FastAPI 应用创建（通过 lifespan 事件与 Canary 生命周期联动）
    2. 自动路由注册（扫描 @web 和 @router 装饰的类和方法）
    3. Uvicorn 服务器启动（异步模式，通过 uvicorn.Server.serve()）

与 Canary 的关系：
    - init():  创建内部 Canary 实例，调用 canary.init() 完成所有服务的初始化和配置加载
    - start(): 创建 FastAPI 应用，通过 lifespan 在服务器启动时调用 canary.start()（on_start 钩子）、
               注册路由、在服务器关闭时调用 canary.stop()（on_end 钩子）

服务器参数（host/port）：
    不从 WebCanary 构造函数或 start() 方法传入，而是由根模块的 @config 类声明：
        @config
        class AppConfig:
            host: str = "0.0.0.0"
            port: int = 8000
    模块在 on_init 阶段加载该配置，start() 时从根模块的 config_instance 读取。
"""
from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from cf import Canary
from cf.core.decorators.module import is_cf_module
from cf.core.decorators.service import is_cf_service
from cf.core.registry.registry import Registry

from cf.web.fastapi.context import RouterContext
from cf.web.fastapi.decorators.router import is_route_method, get_route_info, get_router_prefix
from cf.web.fastapi.decorators.web import is_web, get_web_routers


class WebCanary:
    """
    Web 版 Canary 引擎 —— 为 FastAPI 提供完整的 Canary 生命周期集成。

    使用方式：
        import asyncio
        from cf.web.fastapi import WebCanary

        async def main():
            app = WebCanary(AppModule, fastapi_kwargs={"title": "My API"})
            await app.init(config_file_path=".env")  # 初始化所有服务、加载配置
            await app.start()                         # 启动 FastAPI 服务器（阻塞直到停止）

        asyncio.run(main())
    """

    def __init__(
        self,
        target: type,
        *,
        fastapi_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """
        初始化 WebCanary。

        参数：
            target:          根模块/服务类，必须被 @module 或 @service 装饰
                             也应该是带有 @web 装饰器的类（否则没有路由）
            fastapi_kwargs:  （可选）传递给 FastAPI() 构造函数的额外参数字典
                             如：{"title": "My API", "version": "1.0.0"}
        """
        # 根目标类（如 AppModule）
        self._target = target
        # FastAPI 应用构造参数（如 title, version, docs_url 等）
        self._fastapi_kwargs = fastapi_kwargs or {}
        # 内部 Canary 实例，在 init() 中创建
        self._canary: Canary | None = None

    async def init(self, config_file_path: str = ".env") -> None:
        """
        初始化阶段 —— 创建内部 Canary 并执行服务发现、校验、初始化。

        此阶段完成：
        - 递归收集所有服务和模块
        - 依赖校验
        - 拓扑排序
        - 依赖注入
        - 配置加载
        - 调用各服务的 @on_init 钩子

        参数：
            config_file_path: 根级 .env 文件路径
        """
        # 创建内部 Canary 引擎实例
        self._canary = Canary(self._target)
        # 委托给 Canary.init() 完成全部初始化工作
        await self._canary.init(config_file_path)

    async def start(self) -> None:
        """
        启动阶段 —— 创建 FastAPI 应用，通过 lifespan 事件联动 Canary 生命周期。

        生命周期流程：
        1. 从根模块的 config_instance 读取 host 和 port（默认 "0.0.0.0":8000）
        2. 创建 FastAPI 应用，配置 lifespan 事件处理器
        3. lifespan 启动阶段：
           a. 调用 canary.start() —— 触发所有服务的 @on_start 钩子
           b. 注册所有由 @web 和 @router 标记的路由到 FastAPI 应用
        4. 服务器运行（uvicorn.Server.serve()）—— 处理 HTTP 请求
        5. lifespan 停止阶段：
           调用 canary.stop() —— 逆序触发所有服务的 @on_end 钩子

        服务器参数：
            host 和 port 从根模块的 @config 配置类中读取：
                @config
                class AppConfig:
                    host: str = "0.0.0.0"
                    port: int = 8000
        """
        canary = self._canary

        # 从根模块的 config_instance 读取 host 和 port
        root_entry = canary._registry.get_by_class(self._target)
        root_config = root_entry.config_instance
        # 如果根模块未声明 config，使用默认值
        host = getattr(root_config, "host", "0.0.0.0") if root_config else "0.0.0.0"
        port = getattr(root_config, "port", 8000) if root_config else 8000

        # 定义 FastAPI lifespan —— 将 Canary 生命周期与 HTTP 服务器生命周期绑定
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # --- 服务器启动阶段 ---
            # 调用所有服务的 @on_start 钩子
            await canary.start()
            # 将注册表挂载到 app.state，方便中间件和路由处理器访问
            app.state.cf_registry = canary._registry
            # 注册所有由 @web 和 @router 声明的 FastAPI 路由
            _register_routes(app, canary._registry)
            # yield 表示服务器已准备好接收请求
            yield
            # --- 服务器停止阶段 ---
            # 逆序调用所有服务的 @on_end 钩子（优雅关闭）
            await canary.stop()

        # 创建 FastAPI 应用，绑定 lifespan 事件
        fastapi_app = FastAPI(lifespan=lifespan, **self._fastapi_kwargs)

        # 使用 uvicorn 的异步服务器模式（非阻塞，通过 serve() 返回协程）
        import uvicorn
        config = uvicorn.Config(fastapi_app, host=host, port=port)
        server = uvicorn.Server(config)
        # 启动服务器（阻塞当前协程，直到服务器停止）
        await server.serve()


def _register_routes(app: FastAPI, registry: Registry) -> None:
    """
    扫描注册表中所有 @web 装饰的类，将其路由注册到 FastAPI 应用。

    处理逻辑：
        1. 遍历每个注册项，检查其类是否为 @web 装饰的
        2. 对于 @web(routers=[...]) 中声明的路由类：
           - 实例化路由类（传入 RouterContext）
           - 根据 @router(prefix=...) 的 prefix 注册该类中的 HTTP 方法
        3. 对于 @web 类自身（无 routers 或作为模块的 @web 类）：
           - 如果类是 @module 或 @service，注册其自身定义的 HTTP 方法路由
        4. 如果类既有 routers 又是 @module，则同时注册 routers 和自身方法

    参数：
        app:      FastAPI 应用实例（路由将注册到该实例）
        registry: 全局注册表（包含所有已注册的服务和模块）
    """
    for entry in registry.all_entries():
        cls = entry.cls
        # 只处理带 @web 装饰器的类
        if not is_web(cls):
            continue

        # 获取 @web(routers=[...]) 中声明的路由类列表
        routers = get_web_routers(cls)

        # 注册路由类中的 HTTP 方法
        for router_cls in routers:
            # 获取路由器前缀（由 @router(prefix="/api") 声明）
            prefix = get_router_prefix(router_cls)
            # 创建 RouterContext：让路由类可以访问所属服务实例 + 解决依赖
            ctx = RouterContext(entry.instance, registry)
            router_instance = router_cls(ctx)
            # 注册该路由类中的 @get/@post/@put/@delete/@patch 方法
            _register_instance_routes(app, router_instance, prefix)

        # 注册 @web 类自身的 HTTP 方法（无 routers 时，或模块本身有路由方法时）
        if not routers and (is_cf_module(cls) or is_cf_service(cls)):
            _register_instance_routes(app, entry.instance, "")

        # 如果 @web 类既有 routers 又是模块，额外注册其自身定义的方法
        if routers and is_cf_module(cls):
            _register_instance_routes(app, entry.instance, "")


def _register_instance_routes(app: FastAPI, instance: object, prefix: str) -> None:
    """
    扫描实例类中的所有 @get/@post/@put/@delete/@patch 方法并注册为 FastAPI 路由。

    参数：
        app:      FastAPI 应用实例
        instance: 存在路由方法的类实例（服务实例或路由类实例）
        prefix:   路由前缀（如 "/api"），会拼接到每个路径前面
    """
    # inspect.getmembers 遍历类的所有成员，筛选出方法
    for _, method in inspect.getmembers(instance.__class__, inspect.isfunction):
        # 只处理被 @get/@post/@put/@delete/@patch 装饰的方法
        if not is_route_method(method):
            continue

        # 获取路由信息：HTTP 方法、路径、额外参数
        http_method, path, kwargs = get_route_info(method)

        # 拼接完整路径：prefix + path
        full_path = prefix.rstrip("/") + "/" + path.lstrip("/")
        # 去除末尾多余的斜杠（除了根路径 "/"）
        if full_path.endswith("/") and full_path != "/":
            full_path = full_path.rstrip("/")

        # 将方法绑定到实例（确保 self 正确传递）
        bound = getattr(instance, method.__name__)
        # 注册到 FastAPI 应用
        app.add_api_route(
            path=full_path,
            endpoint=bound,
            methods=[http_method],
            **kwargs,
        )
