from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class User(IDMixin, TimestampMixin, Base):
    __tablename__ = 'users'

    ROLE_ADMIN = "admin"
    ROLE_AGENT = "agent"

    username: Mapped[str] = mapped_column(String(50),unique=True,nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="agent", nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)