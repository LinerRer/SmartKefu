from typing import Optional

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin
from app.models.kb import KnowledgeBase
from app.models.user import User


class Conversation(IDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    STATUS_AI = "ai"
    STATUS_HUMAN = "human"
    STATUS_CLOSED = "closed"

    visitor_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_AI, nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    kb: Mapped["KnowledgeBase"] = relationship(back_populates="conversations")
    agent: Mapped[Optional["User"]] = relationship()
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    feedback: Mapped[Optional["Feedback"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

class Message(IDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    ROLE_VISITOR = "visitor"
    ROLE_AI = "ai"
    ROLE_AGENT = "agent"


    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20),nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")



