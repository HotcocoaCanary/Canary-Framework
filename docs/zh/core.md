# 核心概念

本文档解释 Canary 框架的核心设计原则和内部架构。

## 设计原则

### 1. 装饰器驱动

框架使用装饰器保持代码简洁和声明式：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    pass
```

无需复杂的配置文件，您的代码本身就是配置。

### 2. 异步优先

一切都围绕 async/await 构建以实现高性能：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    async def do_something(self):
        await some_async_operation()
```

### 3. 注解驱动依赖

依赖通过 Python 类型注解声明，取代旧的 `deps` 参数。这使得依赖关系更直观，IDE 也能提供更好的支持：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    db: DatabaseService
    cache: CacheService
```

### 4. 约定优于配置

合理的默认值减少样板代码：
- 服务名称自动生成为 `类名 + "Service"`
- 模块名称自动生成为 `类名 + "Module"`
- 路由名称自动生成为 `类名 + "Router"`
- 依赖通过类型注解自动检测
- 路由参数从函数签名自动绑定

### 5. 可组合性

通过组合简单模块构建复杂系统：

```python
from canary_framework import module
from canary_framework.core import ModuleBase

@module(services=[AuthModule, PostsModule, CommentsModule])
class App(ModuleBase):
    pass
```

## 架构概述

```
┌─────────────────────────────────────────────────────────┐
│                      应用程序                          │
├─────────────────────────────────────────────────────────┤
│                      模块                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 认证模块    │  │ 文章模块    │  │   ...        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      服务                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   @service   │  │   @service   │  │   @router   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      引擎                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 注册表   │  │ 注入器   │  │ 生命周期  │  │ 钩子    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Starlette/ASGI                          │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 装饰器

装饰器将普通类转换为框架感知的组件：

- `@service()`：将类标记为服务（无参数，自动命名 `ClassName+"Service"`）
- `@module(*, services=[...])`：将类标记为模块（仅 `services` 参数，自动命名 `ClassName+"Module"`）
- `@router(prefix="", *, tags=None)`：将类标记为路由（无 `name`/`deps` 参数，自动命名 `ClassName+"Router"`）
- `@get/@post 等`：将方法标记为路由处理程序
- `@after_config 等`：将方法标记为生命周期钩子

### 2. 基类

装饰类必须显式继承自基类：

- `ServiceBase`：带有生命周期方法的服务基类
- `ModuleBase`：协调服务的模块基类（继承 `ServiceBase`）
- `RouterBase`：带有 ASGI 集成的路由基类（继承 `ServiceBase`）

### 3. 引擎

引擎管理框架的核心操作：

- **Registry**：服务注册和查找（支持父子继承）
- **injector**：`topological_sort(registry)` — 使用 `resolve_deps()` 的依赖拓扑排序
- **hooks**：生命周期钩子发现（`find_hooks`）和执行

## 工作原理：模块启动

让我们跟踪启动模块时发生的情况：

### 步骤 1：模块实例化

```python
app = App()
```

- 创建模块类的实例
- 类通过装饰器要求并验证为 `ModuleBase` 的子类

### 步骤 2：配置（核心 DI 阶段）

```python
await app.configure(config_instance)  # config 必须是 CanaryConfig 实例或 None
```

1. 设置 `config` 属性，初始化日志
2. 创建 `Registry` 实例
3. 对 `services` 列表中的每个类调用 `_register_entry_with_deps()`：
   - 检查幂等性（已在注册表则跳过）
   - 注册到 Registry
   - 通过 `resolve_deps(cls)` 读取类型注解，递归注册依赖
4. `topological_sort(registry)`：使用 `resolve_deps()` 构建依赖图，执行 Kahn 算法排序
5. 按拓扑顺序创建所有服务的实例
6. 按拓扑顺序注入依赖：对每个实例调用 `resolve_deps()`，通过 `setattr(inst, attr_name, dep_instance)` 注入
7. 通过 `setattr(self, entry.cls.__name__, inst)` 将子服务挂载到模块（用原始类名）
8. 按拓扑顺序调用每个子服务的 `configure(config_instance)`
9. 运行模块的 `@after_config` 钩子

### 步骤 3：初始化

```python
await app.init()
```

1. 运行模块的 `@after_init` 钩子
2. 按拓扑顺序调用每个子服务的 `init()`

### 步骤 4：启动

```python
await app.startup()
```

1. 运行模块的 `@before_startup` 钩子
2. 按拓扑顺序调用每个子服务的 `startup()`

### 步骤 5：请求处理

模块充当 ASGI 应用：
- 从服务中收集所有路由
- 创建 Starlette 路由
- 将子路由挂载在其服务名称处
- 将请求路由到处理程序

### 步骤 6：关闭

```python
await app.shutdown()
```

1. 运行模块的 `@before_shutdown` 钩子
2. 按逆拓扑顺序调用每个子服务的 `shutdown()`

## 元数据系统

框架将元数据存储在装饰类上：

```python
from canary_framework import service
from canary_framework.core import ServiceBase

@service()
class MyService(ServiceBase):
    pass

# 元数据存储为属性
hasattr(MyService, "__cf_service__")  # True
hasattr(MyService, "__cf_service_meta__")  # True
```

元数据类：
- `ServiceMeta(name: str)`：服务元数据（无 `deps` 字段）
- `ModuleMeta(name: str, services: list[type])`：模块元数据（扩展 ServiceMeta）
- `RouterMeta(name: str, prefix: str, tags: list[str], routes: list)`：路由元数据（扩展 ServiceMeta）

## 标记系统

标记标识类的类型。框架使用单一的 `CF_SERVICE_MARKER` 标记：

- `CF_SERVICE_MARKER = "__cf_service__"`：标识所有框架装饰类（服务、模块和路由共享此标记）

辅助函数：
- `is_cf_service(cls)`：检查类是否为服务
- `is_cf_module(cls)`：检查类是否为模块
- `is_cf_router(cls)`：检查类是否为路由

## 依赖注入流程

```
1. 收集模块的 services 列表中的所有服务
   ↓
2. 递归注册（_register_entry_with_deps）
   ├─ 注册到 Registry
   └─ resolve_deps(cls) → 过滤 CF_SERVICE_MARKER → 递归注册依赖
   ↓
3. topological_sort(registry)
   ├─ 遍历所有条目，通过 resolve_deps() 获取依赖
   ├─ 构建入度表和邻接表
   └─ Kahn 算法排序
   ↓
4. 按拓扑顺序创建实例
   ↓
5. 注入依赖（for attr_name, dep_cls in resolve_deps(type(inst)).items():
   setattr(inst, attr_name, dep_instance)）
   ↓
6. 模块挂载子服务（setattr(self, entry.cls.__name__, inst)）
   ↓
7. 运行生命周期
```

## resolve_deps 函数

`resolve_deps(cls)` 是 DI 系统的核心函数，位于 `canary_framework.common.markers`：

```python
def resolve_deps(cls: type) -> dict[str, type]:
    """从类的类型注解中解析依赖映射。

    使用 typing.get_type_hints 获取类型注解，
    过滤出被 @service/@module/@router 装饰的类型。
    返回 {属性名: 依赖类型}。
    """
```

该函数被 `topological_sort()` 和 `ModuleBase._register_entry_with_deps()` 调用，
替代了旧版中手动指定的 `deps` 参数。

## ASGI 集成

框架与 Starlette 集成以提供 ASGI 支持：

1. `RouterBase` 收集路由处理程序
2. 将它们转换为 Starlette `Route` 对象
3. 创建 Starlette `Router`
4. `ModuleBase` 挂载子路由
5. 模块充当 ASGI 应用

## 错误处理

框架定义自定义异常：

- `CanaryFrameworkError`：基本异常
- `DependencyInjectionError`：DI 期间错误
- `CircularDependencyError`：检测到循环依赖
- `LifecycleHookError`：生命周期钩子中的错误
- `ServiceNotFoundError`：注册表中未找到服务
- `ConfigurationError`：配置错误

## 可扩展性

框架设计为可扩展的：

- 通过继承 `ServiceBase` 创建自定义基类
- 构建包装内置装饰器的自定义装饰器
- 创建打包相关服务的组合模块
- 与任何 ASGI 兼容的服务器集成

## 性能考虑

- **启动**：O(n + e) 由于拓扑排序（n=服务数，e=依赖边数）
- **运行时**：服务查找 O(1)
- **内存**：服务是单例，内存效率高
- **请求**：由 Starlette 处理，非常快

## 测试策略

框架设计为可测试的：

- 服务是普通类，易于实例化
- 依赖通过注解声明，易于模拟
- 生命周期方法可以单独调用
- 没有全局状态，测试隔离
