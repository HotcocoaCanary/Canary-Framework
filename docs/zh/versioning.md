# 版本与兼容性

Canary Framework 从 1.0.0 起遵循[语义化版本](https://semver.org/lang/zh-CN/)。1.0 之前的版本
属于摸索阶段，破坏性变更不受约束。

## 版本号的含义

| 版本 | 可能包含 |
|---|---|
| 修订版 `1.0.x` | 缺陷修复与文档。不新增公开名字。 |
| 次版本 `1.x.0` | 新功能与弃用。已有代码继续可用。 |
| 主版本 `x.0.0` | 破坏性变更，每一项都在变更日志中列出并给出迁移方式。 |

## 公开 API {#public-api}

稳定性承诺覆盖：

- 从 `canary_framework` 导出的全部名字（即 `__all__`），以及本文档描述的签名与行为；
- 文档所描述情形下抛出的异常类型；
- 生命周期规则：依赖顺序、每个单元的每个阶段只运行一次、`init` 与 `start` 之间的栅栏、
  逆序回收、`stop()` 之后可再次启动。

**不**覆盖：

- `canary_framework.core.*` 下未从 `canary_framework` 重新导出的内容；
- 以下划线开头的名字；
- 异常消息与 note 的文字；
- `Scope` 记录类属性（`phases`、`entered`、`known`、`graph`、`dependents`）的结构。它们用于
  观察与调试，可能在次版本中变化。`Scope.instances`、`Scope.instance()`、`Scope.provide()`、
  `Scope.resolve()` 与 `Scope.key_of()` 在承诺范围内。

## 弃用

公开的名字或行为只在主版本中移除，并且之前至少有一个次版本在使用它时发出
`DeprecationWarning`，指明替代方式。每一项弃用都记录在变更日志中。

## 支持的版本

只有最新的次版本接收修复，包括安全修复。同一主版本内的升级应当可以直接替换。

## Python 版本

每个版本支持的 Python 版本以 PyPI 上列出的为准（目前为 3.12 至 3.15）。已到生命周期终点的
Python 版本可能在次版本中停止支持，并在变更日志中说明。

## 发布

发布由在 `main` 上推送 `vX.Y.Z` tag 触发。每个版本的说明取自
[变更日志](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CHANGELOG.md)中对应的
一节，后附已合并的 PR 列表。
