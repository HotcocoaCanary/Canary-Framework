# 依赖注入

用类级类型注解声明依赖：

```python
@service()
class Repository(ServiceBase):
    pass

@router()
class Api(RouterBase):
    repository: Repository
```

引擎解析传递依赖、校验方向、拓扑排序、每个本地类只实例化一次，并将实例赋给注解属性。

## 方向规则

- Service → Service：允许。
- Router → Service：允许。
- Service → Router/Module：拒绝。
- Router → Router/Module：拒绝。
- Module 组合 `children` 并建立作用域，不是向上依赖目标。

## 作用域

子作用域复用匹配的父 Service；缺失 Service 在本地创建，兄弟作用域隔离。多个兄弟需要共享时，将 Service 提升到最近共同父节点。循环依赖与无法解析的前向引用会在初始化期间给出带上下文的框架错误。
