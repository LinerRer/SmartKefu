"""FastAPI 依赖注入：current_user + 角色校验。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """从 token 解析 current_user。失败抛 401。"""
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="无效的 token")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的 token payload")
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_role(*roles: str):
    """角色权限装饰器：@require_role("admin") 或 @require_role("admin", "agent")。"""
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail=f"需要角色 {roles}，当前 {current_user.role}")
        return current_user
    return checker
