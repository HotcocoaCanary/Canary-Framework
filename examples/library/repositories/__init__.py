"""数据访问层：书籍 / 读者 / 借阅 三个仓库。"""

from .book import BookRepository
from .loan import LoanRepository
from .member import MemberRepository

__all__ = ["BookRepository", "LoanRepository", "MemberRepository"]
