# -*- coding: utf-8 -*-
"""安全工具测试：密码哈希 + JWT 签发/验签/篡改/过期。"""
from datetime import timedelta

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


class TestPassword:
    def test_hash_not_plaintext(self):
        h = hash_password("secret123")
        assert h != "secret123"
        assert h.startswith("$2")          # bcrypt 指纹

    def test_same_password_different_hash(self):
        """bcrypt 自带随机盐：同一密码两次哈希结果不同（防彩虹表）。"""
        assert hash_password("secret123") != hash_password("secret123")

    def test_verify(self):
        h = hash_password("secret123")
        assert verify_password("secret123", h) is True
        assert verify_password("wrong", h) is False


class TestJwt:
    def test_token_roundtrip(self):
        token = create_access_token(data={"sub": "42", "role": "agent"})
        payload = verify_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "agent"
        assert "exp" in payload            # 必须带过期声明

    def test_tampered_token_rejected(self):
        """死路：改一个字符，验签必须失败返回 None。"""
        token = create_access_token(data={"sub": "42"})
        bad = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
        assert verify_token(bad) is None

    def test_expired_token_rejected(self):
        """死路：签发时就已过期的 token，验签必须失败。"""
        token = create_access_token(
            data={"sub": "42"}, expires_delta=timedelta(seconds=-10))
        assert verify_token(token) is None

    def test_foreign_secret_rejected(self):
        """死路：别的密钥签的 token 不认（伪造攻击）。"""
        from jose import jwt
        forged = jwt.encode({"sub": "1", "role": "admin"},
                            "wrong-secret", algorithm="HS256")
        assert verify_token(forged) is None