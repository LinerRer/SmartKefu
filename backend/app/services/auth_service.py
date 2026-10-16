"""认证服务：登录验证 + 用户注册。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.security import hash_password, verify_password
from app.models.user import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """校验用户名密码，成功返回 User 对象，失败返回 None。"""
    user = db.query(User).filter_by(username=username).first()
    if not user:
        logger.warning(f"登录失败：用户 {username} 不存在")
        return None
    if not verify_password(password, user.password_hash):
        logger.warning(f"登录失败：用户 {username} 密码错误")
        return None
    if user.status != 1:
        logger.warning(f"登录失败：用户 {username} 已禁用")
        return None
    logger.info(f"登录成功：用户 {username} (id={user.id}, role={user.role})")
    return user


def register_user(db: Session, username: str, password: str, role: str = "agent") -> User:
    """注册新用户：用户名唯一，密码加密存储。"""
    # 检查用户名是否已存在
    existing = db.query(User).filter_by(username=username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"用户名 {username} 已被注册")

    # 安全约定（v1.1）：注册入口永远只产出 agent 角色账号，
    # admin 账号只能由运维通过 init_admin.py 直连数据库创建。
    # 在服务层兜底，杜绝"注册接口传 role=admin 自我提权"。
    role = User.ROLE_AGENT

    # 创建用户
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"注册成功：用户 {username} (id={user.id}, role={role})")
    return user
