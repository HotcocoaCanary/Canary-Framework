# 核心概念

本文档解释 Canary 框架的核心设计原则和内部架构。

## 设计原则

### 1. 装饰器驱动

框架使用装饰器保持代码简洁和声明式：

```python
@service(name="my_service")
class MyService:
    pass
```

无需复杂的配置文件，您的代码本身就是配置。

### 2. 异步优先

一切都围绕 async/await 构建以实现高性能：

```python
@service(name="my_service")
class MyService:
    async def do_something(self):
        await some_async_operation()
```

### 3. 显式依赖

依赖项显式声明，使您的代码更易于理解和测试：

```python
@service(name="my_service", deps=[DatabaseService, CacheService])
class MyService:
    pass
```

### 4. 约定优于配置

合理的默认值减少样板代码：
- 依赖项使用 snake_case 名称自动注入
- 生命周期方法遵循标准模式
- 路由自动挂载在可预测的路径上

### 5. 可组合性

通过组合简单模块构建复杂系统：

```python
@module(name="app", services=[AuthModule, PostsModule, CommentsModule])
class AppModule:
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
│  │   服务      │  │   服务      │  │   路由      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                      引擎                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ 注册表   │  │ 注入器   │  │ 生命周期   │  │ 钩子    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Starlette/ASGI                          │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 装饰器

装饰器将普通类转换为框架感知的组件：

- `@service`：将类标记为服务
- `@module`：将类标记为模块
- `@router`：将类标记为路由
- `@get/@post 等`：将方法标记为路由处理程序
- `@after_config 等`：将方法标记为生命周期钩子

### 2. 基类

装饰类自动继承自基类：

- `ServiceBase`：带有生命周期方法的服务基类
- `ModuleBase`：协调服务的模块基类
- `RouterBase`：带有 ASGI 集成的路由基类

### 3. 引擎

引擎管理框架的核心操作：

- **注册表**：服务注册和查找
- **注入器**：依赖注入和拓扑排序
- **钩子**：生命周期钩子发现和执行
- **工具**：辅助函数（名称转换等）

## 工作原理：模块启动

让我们跟踪启动模块时发生的情况：

### 步骤 1：模块实例化

```python
app = AppModule()
```

- 创建模块类的实例
- 类通过装饰器继承自 `ModuleBase`

### 步骤 2：配置

```python
await app.configure(config)
```

1. 从模块的 `services` 列表中收集所有服务
2. 通过遍历服务依赖关系构建依赖图
3. 执行拓扑排序以确定启动顺序
4. 创建所有服务的实例
5. 将依赖项注入每个服务
6. 按顺序调用每个服务的 `configure()`
7. 运行 `@after_config` 钩子

### 步骤 3：初始化

```python
await app.init()
```

1. 按顺序调用每个服务的 `init()`
2. 运行 `@after_init` 钩子

### 步骤 4：启动

```python
await app.startup()
```

1. 运行 `@before_startup` 钩子
2. 按顺序调用每个服务的 `startup()`

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

1. 运行 `@before_shutdown` 钩子
2. 按相反顺序调用每个服务的 `shutdown()`

## 元数据系统

框架将元数据存储在装饰类上：

```python
@service(name="my_service", deps=[DatabaseService])
class MyService:
    pass

# 元数据存储为属性
hasattr(MyService, "__cf_service__")  # True
hasattr(MyService, "__cf_service_meta__")  # True
```

元数据类：
- `ServiceMeta`：服务的元数据
- `ModuleMeta`：模块的元数据（扩展 ServiceMeta）
- `RouterMeta`：路由的元数据（扩展 ServiceMeta）

## 标记系统

标记标识类的类型：

- `__cf_service__`：标识服务类
- `__cf_module__`：标识模块类
- `__cf_router__`：标识路由类

辅助函数：
- `is_cf_service()`：检查类是否为服务
- `is_cf_module()`：检查类是否为模块
- `is_cf_router()`：检查类是否为路由

## 依赖注入流程

```
1. 收集所有服务
   ↓
2. 在注册表中注册
   ↓
3. 构建依赖图
   ↓
4. 拓扑排序
   ↓
5. 创建实例
   ↓
6. 注入依赖项
   ↓
7. 运行生命周期
```

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

## 可扩展性

框架设计为可扩展的：

- 通过继承 `ServiceBase` 创建自定义基类
- 构建包装内置装饰器的自定义装饰器
- 创建打包相关服务的组合模块
- 与任何 ASGI 兼容的服务器集成

## 性能考虑

- **启动**：O(n log n) 由于拓扑排序
- **运行时**：服务查找 O(1)
- **内存**：服务是单例，内存效率高
- **请求**：由 Starlette 处理，非常快

## 测试策略

框架设计为可测试的：

- 服务是普通类，易于实例化
- 依赖项显式，易于模拟
- 生命周期方法可以单独调用
- 没有全局状态，测试隔离
