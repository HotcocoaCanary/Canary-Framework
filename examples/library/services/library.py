"""LibraryService —— 借书 / 还书 / 检索 业务逻辑。"""

from canary_framework import cocoa, on_start, on_stop

from ..repositories import BookRepository, LoanRepository, MemberRepository


@cocoa(deps=[BookRepository, MemberRepository, LoanRepository])
class LibraryService:
    @on_start
    def open(self) -> None:
        print("  [LibraryService] 开馆")

    @on_stop
    def close(self) -> None:
        print("  [LibraryService] 闭馆")

    def search(self, keyword: str) -> list[str]:
        return [b["title"] for b in self.book_repository.search(keyword)]

    def borrow(self, member_id: int, book_id: int) -> str:
        member = self.member_repository.get(member_id)
        if member is None:
            return "借阅失败：读者不存在"
        return f"{member['name']}：{self.loan_repository.borrow(member_id, book_id)}"

    def return_book(self, book_id: int) -> str:
        return self.loan_repository.return_book(book_id)
