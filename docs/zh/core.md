# 核心概念

本文档解释 Canary Framework 的核心设计原则和内部架构。

## 设计原则

### 1. 装饰器驱动

框架使用装饰器保持代码简洁和声明式：

```python
@service()
class MyService(ServiceBase):
    pass
```

您的代码本身就是配置 — 无需 XML、JSON 或 YAML。

### 2. 异步优先

一切都围绕 async/await 构建以实现高性能：

```python
@service()
class MyService(ServiceBase):
    async def do_something(self):
        await some_async_operation()
```

### 3. 注解驱动依赖注入

依赖通过 Python 类型注解声明，而非单独的列表：

```python
@service()
class UserService(ServiceBase):
    db: Database      # 自动解析并注入
    cache: Cache      # 自动解析并注入
```

### 4. 自动命名

名称从类名派生 — 无需手动指定字符串：

- `@service()` + 类 `Database` → 名称 `DatabaseService`
- `@module(services=[...])` + 类 `App` → 名称 `AppModule`
- `@router(prefix="/api")` + 类 `Api` → 名称 `ApiRouter`

### 5. 可组合性

通过组合简单模块构建复杂系统：

```python
@module(services=[AuthModule, PostsModule, CommentsModule])
class App(ModuleBase):
    pass
```

## 架构概述

```
┌─────────────────────────────────────────────────────────┐
│                      Application                         │
├─────────────────────────────────────────────────────────┤
│                      Modules                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Auth Module  │  │ Posts Module │  │   ...        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Services                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Service    │  │   Service    │  │   Router     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Engine                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Registry │  │ Resolver │  │ Lifecycle│  │ Hooks  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│                      Starlette/ASGI                      │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 装饰器

装饰器将普通类转换为框架感知的组件：

- `@service()`：将类标记为服务
- `@module(services=[...])`：将类标记为模块容器
- `@router(prefix="", *, tags=None)`：将类标记为路由
- `@get/@post 等`：将方法标记为路由处理器
- `@after_init/@before_startup/@before_shutdown`：将方法标记为生命周期钩子

### 2. 基类

使用 `@service()`、`@module()` 或 `@router()` 装饰的类必须显式继承基类：

- `ServiceBase`：带有生命周期方法的服务基类
- `ModuleBase`：协调服务的模块基类
- `RouterBase`：带有 ASGI 集成的路由基类

### 3. 引擎

引擎管理框架的核心操作：

- **Registry**：服务注册和查找
- **Resolver**：`resolve_deps()` 读取注解以发现依赖
- **Injector**：`topological_sort()` 构建依赖图并排序实例化顺序
- **Hooks**：生命周期钩子的发现和执行

## 依赖注入流程

新的 DI 系统是注解驱动的：

```
1. 遍历声明的服务
   ↓
2. 对每个服务，resolve_deps(cls) 读取类型注解
   ↓
3. 过滤：仅保留标记了 CF_SERVICE_MARKER 的类型
   ↓
4. 递归注册每个发现的依赖
   ↓
5. topological_sort(registry) 构建依赖图
   ↓
6. 按拓扑顺序实例化服务
   ↓
7. 对每个依赖：setattr(instance, annotation_key, dependency_instance)
   ↓
8. 运行生命周期阶段
```

### resolve_deps(cls)

此函数读取类的 `__annotations__` 字典，仅返回类型被 `CF_SERVICE_MARKER` 装饰的条目。例如：

```python
@service()
class Auth(ServiceBase):
    db: Database   # ✓ CF_SERVICE_MARKER — 包含
    x: int         # ✗ 不是服务 — 排除

# resolve_deps(Auth) 返回：{"db": Database}
```

### topological_sort(registry)

使用 Kahn 算法配合 `resolve_deps()` 来：
1. 从所有注册的服务构建完整依赖图
2. 确定实例化顺序
3. 检测循环依赖

### setattr 注入

依赖使用注解键名注入 — 不进行 snake_case 转换：

```python
@service()
class UserService(ServiceBase):
    db: Database   # 注入为 self.db
    repo: UserRepo # 注入为 self.repo
```

## 工作原理：模块启动

让我们跟踪启动模块时发生的情况：

### 步骤 1：模块实例化

```python
app = App()
```

### 步骤 2：初始化

```python
await app.init()
```

1. 从模块的 `services` 列表收集所有服务
2. 对每个服务，调用 `resolve_deps(cls)` 发现注解
3. 递归注册所有发现的依赖类型
4. 调用 `topological_sort(registry)` 确定启动顺序
5. 按顺序实例化所有服务
6. 调用 `setattr` 以注解键名注入每个依赖
7. Config 自动发现：`services` 列表中通过 `issubclass(CanaryConfig)` 检查的类被视为配置
8. 为每个实例设置 `_cf_parent_registry`
9. 按顺序调用每个服务的 `init()`
10. 运行 `@after_init` 钩子

### 步骤 3：启动

```python
await app.init()
```

1. 按顺序调用每个服务的 `init()`
2. 运行 `@after_init` 钩子

### 步骤 3：启动

```python
await app.startup()
```

1. 运行 `@before_startup` 钩子
2. 按顺序调用每个服务的 `startup()`

### 步骤 4：请求处理

模块作为 ASGI 应用：
- 从服务中收集所有路由
- 创建 Starlette 路由
- 在其 prefix 路径上挂载子路由
- 将请求路由到带有自动绑定参数的处理程序

### 步骤 5：关闭

```python
await app.shutdown()
```

1. 运行 `@before_shutdown` 钩子
2. 按逆序调用每个服务的 `shutdown()`

## 元数据系统

框架在装饰类上存储元数据：

```python
@service()
class MyService(ServiceBase):
    pass

hasattr(MyService, "__cf_service__")     # True
hasattr(MyService, "__cf_service_meta__")  # True
```

元数据类：
- `ServiceMeta`：服务元数据（自动生成的名称，从注解解析的依赖）
- `ModuleMeta`：模块元数据（扩展 ServiceMeta，添加 services 列表）
- `RouterMeta`：路由元数据（扩展 ServiceMeta，添加 prefix、tags、routes）

## 标记系统

框架使用 `CF_SERVICE_MARKER` 来标识服务类。类型检查使用 `isinstance` 针对基类进行：

- `isinstance(obj, ServiceBase)`：检查对象是否为框架服务
- `isinstance(obj, ModuleBase)`：检查对象是否为框架模块
- `isinstance(obj, RouterBase)`：检查对象是否为框架路由

辅助函数：
- `is_cf_service(cls)`：检查类是否为框架服务
- `is_cf_module(cls)`：检查类是否为框架模块
- `is_cf_router(cls)`：检查类是否为框架路由

## ASGI 集成

框架与 Starlette 集成以提供 ASGI 支持：

1. `RouterBase` 收集带有自动绑定参数信息的路由处理器
2. 将其转换为 Starlette `Route` 对象
3. 创建 Starlette `Router`
4. `ModuleBase` 和 `RouterBase` 继承 `ServiceBase.__call__`，处理 ASGI 请求和 lifespan 事件
5. 模块作为 ASGI 应用

## 错误处理

框架定义自定义异常：

- `CanaryFrameworkError`：基础异常
- `DependencyInjectionError`：DI 期间错误
- `CircularDependencyError`：检测到循环依赖
- `LifecycleHookError`：生命周期钩子错误
- `ServiceNotFoundError`：注册表中未找到服务

## 可扩展性

框架设计为可扩展的：

- 通过继承 `ServiceBase` 创建自定义基类
- 构建包装内置装饰器的自定义装饰器
- 创建打包相关服务的组合模块
- 与任何 ASGI 兼容的服务器集成

## 性能考虑

- **启动**：由于拓扑排序，时间复杂度为 O(n log n)
- **运行时**：服务查找 O(1)
- **内存**：服务是单例，内存使用高效
- **请求**：由 Starlette 处理，速度极快

## 测试策略

框架设计为可测试的：

- 服务是普通类，易于实例化
- 依赖通过注解显式声明，易于模拟
- 生命周期方法可单独调用
- 无全局状态，测试隔离
