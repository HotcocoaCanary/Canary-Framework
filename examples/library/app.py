"""LibraryApp —— 根单元：把业务层组装成整个应用。"""

from canary_framework import Canary, dep, start

from .services import LibraryService


class LibraryApp(Canary):
    library = dep(LibraryService)

    @start
    def banner(self) -> None:
        print("  [LibraryApp] 系统上线")
