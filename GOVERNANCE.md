# Governance / 项目治理

## 角色 / Roles

**维护者 / Maintainer** — [@HotcocoaCanary](https://github.com/HotcocoaCanary)（张文博）。
负责审查与合并 PR、发布版本、决定 API 与路线。
Reviews and merges pull requests, cuts releases, and decides on API and direction.

**贡献者 / Contributors** — 任何提交 issue、讨论、文档或代码的人。
Anyone who files an issue, joins a discussion, or contributes docs or code.

当前是单一维护者模式。有持续、高质量贡献的贡献者可以被邀请成为共同维护者，届时本文件会
同步更新。
The project currently has a single maintainer. Contributors with sustained, high-quality
contributions may be invited to co-maintain; this document will be updated when that happens.

## 决策方式 / How decisions are made

- **日常改动** 通过 PR 完成，由维护者审查合并。
  Everyday changes go through pull requests reviewed and merged by the maintainer.
- **新 API 或行为变化** 先在 [Discussions · Ideas](https://github.com/HotcocoaCanary/Canary-Framework/discussions/categories/ideas)
  或 issue 中讨论，达成一致后再写代码。
  New APIs or behaviour changes are discussed first in Discussions · Ideas or an issue, and
  coded once agreed.
- 存在分歧时由维护者做最终决定，并在讨论中写明理由。
  When opinions differ, the maintainer decides and records the reasoning in the discussion.

## 范围原则 / Scope

核心保持最小：`Canary`、`dep()` 与阶段。判断一个提议是否进入核心，先问：

The core stays minimal: `Canary`, `dep()` and phases. Before anything enters the core, ask:

1. **能否用现有 API 在单元里实现？** 能，就作为用法写进文档，而不是新增 API。
   Can it be built from the existing API inside a unit? If so, it becomes a documented pattern,
   not a new API.
2. **是否改变现有用法？** 1.x 内不做破坏性变更，见
   [版本与兼容性](https://hotcocoacanary.github.io/Canary-Framework/versioning/)。
   Does it change existing usage? 1.x makes no breaking changes; see
   [Versioning](https://hotcocoacanary.github.io/Canary-Framework/versioning/).
3. **是否引入第三方依赖？** 核心保持零依赖；集成放在独立的包里。
   Does it add a third-party dependency? The core stays dependency-free; integrations live in
   separate packages.

## 路线 / Roadmap

计划中的工作以 [Milestones](https://github.com/HotcocoaCanary/Canary-Framework/milestones)
跟踪，方向性的讨论在 Discussions 进行。
Planned work is tracked as Milestones; direction is discussed in Discussions.

## 行为准则 / Code of Conduct

所有参与者须遵守 [行为准则](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CODE_OF_CONDUCT.md)。
Everyone taking part is expected to follow the [Code of Conduct](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/CODE_OF_CONDUCT.md).
