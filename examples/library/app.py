"""LibraryApp —— 根单元：把业务层组装成整个应用。"""

from canary_framework import cocoa, on_start

from .services import LibraryService


@cocoa(deps=[LibraryService])
class LibraryApp:
    @on_start
    def banner(self) -> None:
        print("  [LibraryApp] 系统上线")
