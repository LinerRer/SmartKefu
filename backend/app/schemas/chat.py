from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    kb_id: int


class ChatBody(BaseModel):
    token: str = Field(..., min_length=8, max_length=64)
    question: str = Field(..., min_length=1, max_length=500)
