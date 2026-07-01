# 安全策略 / Security Policy

## 报告漏洞 / Reporting a Vulnerability

如果你发现安全漏洞，请**不要**创建公开 Issue。请通过以下方式私下报告：

If you discover a security vulnerability, please do **not** open a public issue.
Report it privately via either of:

- 发送邮件至 / Email: **Hotcocoa.Canary@outlook.com**
- 或在 GitHub 上通过 [私有安全报告 / Private security advisory](https://github.com/HotcocoaCanary/Canary-Framework/security/advisories/new) 提交

## 处理流程 / Process

1. 我们将在 **48 小时**内确认收到报告。 / We acknowledge the report within **48 hours**.
2. 我们将在 **7 天**内提供初步评估。 / We provide an initial assessment within **7 days**.
3. 修复后我们将在 GitHub 发布安全公告。 / After a fix, we publish a security advisory on GitHub.

## 支持的版本 / Supported Versions

当前 **0.5.x** 处于积极维护，安全修复在该线上发布。详见[版本策略](#版本策略--versioning-policy)。

The **0.5.x** line is under active maintenance; security fixes ship on this line.

| 版本 / Version | 支持状态 / Status          |
| -------------- | -------------------------- |
| `0.5.x`        | ✅ 积极维护 / Actively maintained |
| `< 0.5`        | ❌ 已停止维护 / End of life  |

## 版本策略 / Versioning Policy

只要**核心设计理念不变**（service 为最小单元、module 组合 service 且 module 即 service、
基于类型注解的依赖注入、装饰器式 API），我们就留在 **0.5.x** 线上持续维护与迭代——
新特性与修复以 `0.5.x` 补丁/小版本发布，**不因单纯的内部重构或行为收敛而抬升大版本号**。
只有当底层设计理念发生根本改变时，版本线才会前进。

As long as the **core design philosophy is unchanged** — service is the smallest unit;
a module composes services and *is* a service; dependency injection via type annotations;
a decorator-driven API — we stay on the **0.5.x** line: features and fixes ship as `0.5.x`
releases, and **internal refactors or behavior tightening alone do not bump the major/minor
line**. The version line only advances when the fundamental design changes.
