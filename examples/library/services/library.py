"""LibraryService —— 借书 / 还书 / 检索 业务逻辑。"""

from canary_framework import Canary, dep, start, stop

from ..repositories import BookRepository, LoanRepository, MemberRepository


class LibraryService(Canary):
    books = dep(BookRepository)
    members = dep(MemberRepository)
    loans = dep(LoanRepository)

    @start
    def open(self) -> None:
        print("  [LibraryService] 开馆")

    @stop
    def close(self) -> None:
        print("  [LibraryService] 闭馆")

    def search(self, keyword: str) -> list[str]:
        return [b["title"] for b in self.books.search(keyword)]

    def borrow(self, member_id: int, book_id: int) -> str:
        member = self.members.get(member_id)
        if member is None:
            return "借阅失败：读者不存在"
        return f"{member['name']}：{self.loans.borrow(member_id, book_id)}"

    def return_book(self, book_id: int) -> str:
        return self.loans.return_book(book_id)
