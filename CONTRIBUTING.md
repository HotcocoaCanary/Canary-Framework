# Contributing / 贡献指南

感谢你对 Canary Framework 的关注！欢迎贡献代码、文档、测试或提出 bug。
Thank you for your interest in Canary Framework! Contributions of code, docs, tests, and
bug reports are all welcome.

## 环境搭建 / Development setup

```bash
git clone https://github.com/HotcocoaCanary/Canary-Framework.git
cd Canary-Framework
uv sync --extra dev --extra web
```

## 开发流程 / Workflow

1. Fork 本仓库，从 `main` 创建功能分支 / Fork the repo and branch from `main`
2. 编写代码与测试 / Write code and tests
3. 本地跑通全部检查与测试 / Run all checks and tests locally:

```bash
uv run ruff check src/ tests/               # lint
uv run ruff format --check src/ tests/      # 格式检查（仅检查）/ format check only
uv run mypy src/ tests/                     # 类型检查 / type check
uv run pytest --cov=src/canary_framework --cov-fail-under=70   # 测试 + 覆盖率 / tests + coverage
```

4. 提交 PR 并描述变更 / Open a PR describing the change

## 代码风格 / Code style

- 使用 Python 3.12+ 语法 / Python 3.12+ syntax
- 格式与 lint 交给 ruff / Formatting and linting are handled by ruff
- 类型注解尽量完整 / Complete type annotations wherever possible
- 注释用中文，docstring 中英文均可 / Comments in Chinese; docstrings may be in either language

## 提交信息 / Commit messages

```
类型: 简述
```

`类型` 取值：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`。

## 许可证 / License

贡献的代码将采用 Apache 2.0 许可证。
Contributions are licensed under Apache 2.0.
