# 依赖注入

cocoa 通过 `@cocoa(deps=[...])` 声明依赖。无需额外 DSL，也无需 `__init__` 装配 —— 依赖图
就写在装饰器里。

## 契约

```python
@cocoa(deps=[Database, Cache])
class UserService: ...
```

`deps=[...]` 是一个有序的 cocoa 类型列表。在**构造期**，运行时把每个依赖注入到实例上，
属性名由类名转 snake_case 得到：

| 依赖类型 | 注入属性 |
|---|---|
| `Config` | `self.config` |
| `Database` | `self.database` |
| `UserService` | `self.user_service` |
| `APIService` | `self.api_service` |
| `HTTPServer` | `self.http_server` |

```python
@cocoa(deps=[Database])
class UserService:
    @on_init
    def check(self) -> None:
        assert self.database is not None  # @on_init 时已经注入
```

**注入属于装配，不属于启动**，所以它发生在**构造函数里**：`Canary(Root)` 一返回，线就
接好了。这带来两件事：`@on_init` 能看到自己的协作者（否则它和 `__init__` 几乎没区别）；
装配类的错误（撞名、不是 cocoa、成环、需要构造参数）在你写下 `Canary(Root)` 那一行就抛出，
而不是等到某个 `await`。

不要在 `__init__` 里读注入属性 —— 那时它们还不存在。请用 `@on_init` 或 `@on_start`。

## 值从哪来

单元一律**无参构造**，所以"这个单元需要一个 dsn / 一个 api key / 一个超时时间"不能写成
构造参数，得写成依赖：

```python
@cocoa
class Config:
    def __init__(self) -> None:
        self.dsn = os.environ["DATABASE_URL"]
        self.timeout = 5.0


@cocoa(deps=[Config])
class Database:
    @on_init
    def configure(self) -> None:
        self.pool = ConnectionPool(self.config.dsn, timeout=self.config.timeout)
```

代价要认：**每个参数化的单元因此都依赖一个配置单元**，而这条依赖不是业务上的协作，纯粹
是用来搬运值的。这是这个设计换来"框架能构造每一个单元、失败时能逆序回收"的代价。

配置本身没有任何特殊待遇 —— 它就是一个普通的 `@cocoa`，你想怎么读环境变量、`.env`、
远程配置中心都行（远程的放 `@on_start`，那是 IO）。

## 解析

`Canary(...)` 通过遍历每个根的 `deps=[...]` 建图，并把每个类型实例化一次。未被 `@cocoa`
标记的类型会抛出 `TypeError`。

依赖按具体类对象解析 —— 没有字符串、没有前向引用：

```python
@cocoa(deps=[Database])
class UserService: ...
```

## 共享

每个类型在**单张图内只实例化一次**。当多个单元依赖同一类型时，它们共享同一个实例：

```python
@cocoa
class Config: ...


@cocoa(deps=[Config])
class Database: ...


@cocoa(deps=[Config])
class Cache: ...


@cocoa(deps=[Database, Cache])
class Root: ...


app = Canary(Root)
assert app[Database].config is app[Cache].config  # 同一个 Config
```

共享作用域限于单个 `Canary`。两个独立的 `Canary` 实例会构建两张独立的图。

**类型即身份。** 一个类型在一张图里只有一个实例，所以"两个连不同库的 `Database`"写不
出来 —— 需要两个实例就写两个类。

## 成环

成环会在**构造期**被拒绝。拓扑排序检测到环时抛出 `CircularDependencyError`，并通过
`.cycle` 暴露环上的类型：

```python
@cocoa(deps=[B])
class A: ...


@cocoa(deps=[A])
class B: ...


Canary(A)  # CircularDependencyError: circular dependency detected: A -> B -> A
```

## 撞名

注入属性名由依赖的**类名**派生，与 `deps` 的顺序无关。两个依赖的 snake_case 撞名时抛
`InjectionError`，而不是"后写的赢"：

```python
@cocoa(deps=[KBFileRepository, KbFileRepository])
class Collide: ...

# InjectionError: Collide.kb_file_repository is claimed by more than one source:
#   KBFileRepository, KbFileRepository
```

改名其中一个类即可。缩写会被正确处理（`APIService` → `api_service`）。

## 多根图

给 `Canary` 传入多个根会合并它们的图。根之间共享的依赖仍只实例化一次：

```python
app = Canary(UserService, ReportService)
assert app[UserService].database is app[ReportService].database
```

## 测试时替换依赖

框架**不提供**替换入口。因为注入本来就只是给属性赋值，测试里直接赋值即可：

```python
service = UserService()
service.database = FakeDatabase()      # 就是注入在做的事
await service.some_method()
```

需要连生命周期一起测时，把假实现写成一个 `@cocoa` 单元，用它当根组一张测试专用的图。
