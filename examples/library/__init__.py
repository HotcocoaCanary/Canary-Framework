"""图书馆示例 —— 一个五层的真实依赖图。

每个 ``Canary`` 子类都是最小单元，用 ``dep(...)`` 声明依赖；项目按层组织：

    LibraryApp  →  LibraryService  →  三个 Repository  →  Database  →  Config

启动 ``LibraryApp`` 一个，整棵树自己按依赖序就位，退出时逆序回收。
"""
