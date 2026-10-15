from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


class KBUpdate(BaseModel):
    """仅允许更新描述；名称在业务层锁定，即使传入也会被忽略。"""
    description: str = Field("", max_length=500)


class SearchTestBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    kb_id: int
    top_k: int | None = Field(None, ge=1, le=50)