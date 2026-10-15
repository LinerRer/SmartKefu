from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin
from app.models.conversation import Conversation
from app.models.user import User


class Ticket(IDMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    STATUS_OPEN = "open"
    STATUS_PROCESSING = "processing"
    STATUS_CLOSED = "closed"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    contact: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_OPEN, nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="tickets")
    agent: Mapped[Optional["User"]] = relationship()
    replies: Mapped[list["TicketReply"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class TicketReply(IDMixin, TimestampMixin, Base):
    __tablename__ = "ticket_replies"

    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="replies")
    agent: Mapped[Optional["User"]] = relationship()


class Feedback(IDMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), unique=True, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="feedback")