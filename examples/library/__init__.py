"""图书馆管理系统 —— 一个完整的项目示例（数据库用内存模拟数据）。

每个 ``@cocoa`` 都是最小单元，通过 ``deps=[...]`` 嵌套成依赖图；项目按层组织：

    app.py                  # LibraryApp（根单元，组装顶层）
    services/library.py     # LibraryService（业务层：借书 / 还书 / 检索）
    repositories/           # 数据访问层（Book / Member / Loan）
    database.py             # Database（内存模拟数据）
    config.py               # Config

运行：``PYTHONPATH=src python -m examples.library.main``
"""
