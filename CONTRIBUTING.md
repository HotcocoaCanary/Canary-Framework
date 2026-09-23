# Contributing / 贡献指南

感谢你对 Canary Framework 的关注！欢迎贡献代码、文档、测试或提出 bug。
Thank you for your interest in Canary Framework! Contributions of code, docs, tests, and
bug reports are all welcome.

提问请到 [Discussions · Q&A](https://github.com/HotcocoaCanary/Canary-Framework/discussions/categories/q-a)；
新 API 或行为变化请先到 [Discussions · Ideas](https://github.com/HotcocoaCanary/Canary-Framework/discussions/categories/ideas)
讨论，再写代码（见 [项目治理](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/GOVERNANCE.md)）。
Ask questions in Discussions · Q&A. Propose new APIs or behaviour changes in Discussions · Ideas
before writing code (see [Governance](https://github.com/HotcocoaCanary/Canary-Framework/blob/main/GOVERNANCE.md)).

## 环境搭建 / Development setup

```bash
git clone https://github.com/HotcocoaCanary/Canary-Framework.git
cd Canary-Framework
uv sync --all-extras
uv run pre-commit install
```

## 开发流程 / Workflow

1. Fork 本仓库，从 `main` 创建分支 / Fork the repo and branch from `main`
2. 编写代码与测试 / Write code and tests
3. 本地跑通全部检查 / Run all checks locally:

```bash
uv run ruff check src/ tests/               # lint
uv run ruff format --check src/ tests/      # 格式检查 / format check
uv run mypy src/ tests/                     # 类型检查 / type check
uv run pytest --cov=src/canary_framework --cov-fail-under=95   # 测试 + 覆盖率 / tests + coverage
uv run mkdocs build --strict                # 改了文档时 / when docs changed
```

4. 提交 PR。行为变化须同时更新中英文文档与 `CHANGELOG.md` 的 `[Unreleased]` 一节。
   Open a PR. Behaviour changes must update the English and Chinese docs and the
   `[Unreleased]` section of `CHANGELOG.md`.

## 分支与合并 / Branches and merging

- `main` 受保护：只能通过 PR 合并，CI（测试矩阵、文档构建、PR 标题检查）须全部通过，
  并经维护者审查。
  `main` is protected: changes land through pull requests only, after CI (test matrix, docs
  build, PR title check) passes and the maintainer reviews.
- 只使用 squash 合并，**PR 标题即 main 上的提交信息**。
  Squash merge only — **the PR title becomes the commit message on `main`**.
- `N.x`（如 `1.x`）是维护分支，仅在需要给旧 major 打补丁时创建。
  `N.x` (e.g. `1.x`) are maintenance branches, created only when an older major needs a fix.

## PR 标题 / PR titles

遵循 [Conventional Commits](https://www.conventionalcommits.org/)，由 CI 检查并据此打 label：
Follow Conventional Commits; CI checks the title and labels the PR from it:

```
类型(可选范围)!: 简述
type(optional-scope)!: summary
```

| 类型 / Type | 用途 / Use | Label |
|---|---|---|
| `feat` | 新功能 / New feature | `enhancement` |
| `fix` | 缺陷修复 / Bug fix | `bug` |
| `perf` | 性能 / Performance | `performance` |
| `docs` | 文档 / Documentation | `documentation` |
| `refactor` / `test` / `build` / `ci` / `chore` / `revert` | 其他 / Other | `maintenance` |

`!` 表示破坏性变更，会额外打上 `breaking`。1.x 内不接受破坏性变更。
`!` marks a breaking change and adds `breaking`. Breaking changes are not accepted within 1.x.

## 代码风格 / Code style

- 使用 Python 3.12+ 语法 / Python 3.12+ syntax
- 格式与 lint 交给 ruff / Formatting and linting are handled by ruff
- 类型注解完整，mypy strict 通过 / Complete type annotations; mypy strict passes
- 注释用中文，docstring 首行英文 / Comments in Chinese; docstrings open with an English summary line

## 发布 / Releasing（维护者 / maintainers）

1. 开一个 `chore: 发布 X.Y.Z` 的 PR：更新 `pyproject.toml` 与 `src/canary_framework/__init__.py`
   的版本号，把 `CHANGELOG.md` 的 `[Unreleased]` 改为 `[X.Y.Z] — 日期`。
   Open a `chore: 发布 X.Y.Z` PR that bumps the version in `pyproject.toml` and
   `src/canary_framework/__init__.py`, and renames `[Unreleased]` in `CHANGELOG.md` to
   `[X.Y.Z] — date`.
2. 合并后在 main 上打 tag 并推送 / After merging, tag `main` and push:

   ```bash
   git switch main && git pull
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

3. `Release & Publish` workflow 校验版本、测试、构建；在 Actions 页面批准 `publish`
   环境后发布到 PyPI，并创建 GitHub Release。
   The `Release & Publish` workflow verifies, tests and builds; approve the `publish`
   environment in Actions to publish to PyPI and create the GitHub Release.

## 许可证 / License

贡献的代码将采用 Apache 2.0 许可证。
Contributions are licensed under Apache 2.0.
