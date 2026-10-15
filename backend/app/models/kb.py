from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin


class KnowledgeBase(IDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[int] = mapped_column(Integer, default=1)

    documents: Mapped[list["Document"]] = relationship(back_populates="kb", cascade="all, delete-orphan")
    faqs: Mapped[list["FAQ"]] = relationship(back_populates="kb", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="kb", cascade="all, delete-orphan")

class Document(IDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")

    kb: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(IDMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped["Document"] = relationship(back_populates="chunks")

class FAQ(IDMixin, TimestampMixin, Base):
    __tablename__ = "faqs"

    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1)

    kb: Mapped["KnowledgeBase"] = relationship(back_populates="faqs")
