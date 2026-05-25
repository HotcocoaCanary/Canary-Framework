# 贡献指南

感谢你对 CF (Canary Framework) 的关注！欢迎贡献代码、文档或提出问题。

## 环境搭建

```bash
git clone https://github.com/HotcocoaCanary/Canary-Framework.git
cd Canary-Framework
uv sync --extra dev --extra web
```

## 开发流程

1. Fork 仓库，从 `main` 创建功能分支
2. 编写代码和测试
3. 运行检查和测试：

```bash
uv run ruff check cf/ tests/       # 代码检查
uv run ruff format cf/ tests/      # 代码格式化
uv run mypy cf/                     # 类型检查
uv run pytest --cov=cf              # 运行测试
```

4. 提交 PR，描述变更内容

## 代码风格

- Python 3.12+ 语法
- 使用 ruff 进行格式化和 lint
- 类型注解尽量完整
- 注释使用中文（docstring 中英文均可）

## 提交信息规范

```
类型: 简短描述

类型: feat / fix / docs / refactor / test / chore
```

## 许可证

贡献的代码将采用 Apache 2.0 许可证。
