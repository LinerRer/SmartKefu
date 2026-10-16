"""权限装饰器：保护需要特定角色的接口。"""
from fastapi import Depends, HTTPException
from app.api.v1.deps import get_current_user
from app.models.user import User


def require_role(roles: list[str]):
    """
    权限装饰器：要求用户具有指定角色之一。
    
    用法：
        @router.get("/admin-only")
        def admin_only(current_user: User = Depends(require_role(["admin"]))):
            return {"message": "只有管理员能访问"}
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"需要角色 {roles}，当前角色为 {current_user.role}"
            )
        return current_user
    return role_checker
