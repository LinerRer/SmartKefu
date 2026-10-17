# -*- coding: utf-8 -*-
"""鉴权服务测试：register_user / authenticate_user 的正路、岔路、死路。"""
import pytest
from fastapi import HTTPException

from app.models.user import User
from app.services.auth_service import authenticate_user, register_user


class TestRegister:
    def test_register_success(self, db):
        """正路：注册 agent，入库字段正确、密码非明文。"""
        user = register_user(db, "alice", "secret123")
        assert user.id is not None
        assert user.role == "agent"
        assert user.password_hash != "secret123"      # 铁律：绝不存明文
        assert user.password_hash.startswith("$2")    # bcrypt 指纹

    def test_register_duplicate_username(self, db):
        """死路：同名再注册 → 409。"""
        register_user(db, "alice", "secret123")
        with pytest.raises(HTTPException) as ei:
            register_user(db, "alice", "other123")
        assert ei.value.status_code == 409

    def test_register_role_forced_agent(self, db):
        """安全铁律（v1.1）：注册传任何 role 都强制落 agent，不再报 400。

        旧行为是"非法角色报 400"，但允许传 admin 本身就是提权口子；
        现在服务层无条件强制 agent，从根上堵死。
        """
        user = register_user(db, "bob", "secret123", role="admin")
        assert user.role == "agent"


class TestAuthenticate:
    def test_login_success(self, db):
        register_user(db, "alice", "secret123")
        user = authenticate_user(db, "alice", "secret123")
        assert user is not None and user.username == "alice"

    def test_login_wrong_password(self, db):
        register_user(db, "alice", "secret123")
        assert authenticate_user(db, "alice", "wrong-pass") is None

    def test_login_user_not_exist(self, db):
        assert authenticate_user(db, "ghost", "any") is None

    def test_login_disabled_user(self, db):
        """死路：status!=1 的账号密码对也不许登录。"""
        register_user(db, "alice", "secret123")
        db.query(User).filter_by(username="alice").update({"status": 0})
        db.commit()
        assert authenticate_user(db, "alice", "secret123") is None
