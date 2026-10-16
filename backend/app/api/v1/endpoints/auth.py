"""鉴权路由：登录 + 注册 + 当前用户信息。

权限约定（v1.1 安全加固）：注册接口仅 admin 可调，
匿名自注册（含自注册 admin）的路被彻底堵死；
新账号角色在服务层强制为 agent（见 auth_service.register_user）。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.common import RegisterBody, ResponseSchema, success
from app.services.auth_service import authenticate_user, register_user
from app.api.v1.deps import get_current_user, require_role
from app.models.user import User

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
admin_guard = require_role(User.ROLE_ADMIN)   # 建账号是管理员职责


@router.post("/register", response_model=ResponseSchema, summary="注册（仅管理员可创建账号）")
@limiter.limit("5/minute")
def register(request: Request, body: RegisterBody, db: Session = Depends(get_db),
             current_user: User = Depends(admin_guard)):
    user = register_user(db, body.username, body.password, body.role)
    return success(data={"user_id": user.id, "username": user.username, "role": user.role})


@router.post("/login", response_model=ResponseSchema, summary="登录")
@limiter.limit("5/minute")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return success(data={"access_token": token, "token_type": "bearer", "user_id": user.id, "role": user.role, "username": user.username})


@router.get("/me", response_model=ResponseSchema, summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return success(data={
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    })
