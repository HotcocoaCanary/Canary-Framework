# 架构

## 声明层

`@service`、`@router`、`@module` 校验显式基类继承，并附加不可变元数据。顶层 HTTP 装饰器为处理器附加不可变 route spec，不包装函数。

## 运行层

`ServiceBase` 持有异步生命周期状态机与领域/DI 行为；`RouterBase` 增加路由收集并可成为运行根；`ModuleBase` 持有子节点组合与递归路由收集。

只有已初始化的运行根 Router/Module 通过 ASGI 提供 HTTP 服务。

## 依赖引擎

每个根/作用域有 registry。依赖注解形成经过方向校验的有向图；拓扑顺序驱动初始化/启动，关闭按反序。父查找、兄弟隔离与提升均为显式规则。

## 路由流水线

1. 装饰器创建 `RouteSpec`。
2. Router/Module 遍历创建包含绑定处理器与组合上下文的 `ResolvedRoute`。
3. 参数分析与校验生成 validated routes。
4. OpenAPI 与 ASGI 编译器消费同一序列。
5. 不可变 Assembly 记忆化在已初始化运行根。

单一流水线避免请求绑定与 OpenAPI 对同一路由产生不同解释。
