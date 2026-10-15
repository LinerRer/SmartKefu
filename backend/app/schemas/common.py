from typing import Any, Optional

from pydantic import BaseModel, Field


class ResponseSchema(BaseModel):
    code: int
    message: str = "success"
    data: Any = None


class RegisterBody(BaseModel):
    """注册请求体：用户名必填，角色默认 agent。"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    role: Optional[str] = Field("agent", description="角色：admin 或 agent")


def success(data: Any = None, message: str = "success"):
    return ResponseSchema(code=200, message=message, data=data)