# -*- coding: utf-8 -*-
"""接口级测试：注册/登录/me 全链路 + 权限矩阵（限流→路由→依赖→DB→统一响应）。

权限口径（v1.1 安全加固，与路由层 require_role 一致）：
- 注册：仅 admin（匿名自注册、含自注册 admin 一律 401）；
- kb 读类：admin/agent；kb 写删类：仅 admin；
- stats：仅 admin；
- /kb/public：匿名可访问（访客端选库，最小暴露面）。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.database import get_db
from app.models.base import Base
from tests.conftest import TEST_DB_URL   # 复用测试库地址


@pytest.fixture
def client(engine):
    """engine 来自 conftest（session 级，已建表）；每用例清表 + 重置限流。"""
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with engine.begin() as conn:
        for t in reversed(Base.metadata.sorted_tables):
            conn.execute(t.delete())

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # 路由装饰器用的是 auth 模块自己的 limiter 实例，不是 app.state.limiter，
    # 重置错对象会导致用例间限流计数串扰（第2个用例就被 429 误伤）。
    from app.api.v1.endpoints.auth import limiter as auth_limiter
    auth_limiter.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, username, password):
    """登录拿 token（登录接口是 Form 表单，不是 JSON）。"""
    return client.post("/api/v1/auth/login",
                       data={"username": username, "password": password}
                       ).json()["data"]["access_token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_users(client, db):
    """建 admin + agent 两个账号（必须用 fixture 传入的测试库 Session）。

    admin 走直连 DB 建号（与 init_admin.py 同一条运维路径）：
    服务层 register_user 已强制降为 agent，注册通道永远建不出 admin，
    这正是防提权的设计本身。
    agent 再用 admin 的 token 走 HTTP 注册——顺带验证整条权限链。
    """
    from app.core.security import hash_password
    from app.models.user import User

    db.add(User(username="admin", password_hash=hash_password("adminpass123"),
                role=User.ROLE_ADMIN, status=1))
    db.commit()
    admin_token = _login(client, "admin", "adminpass123")
    client.post("/api/v1/auth/register",
                json={"username": "agent1", "password": "agentpass123"},
                headers=_bearer(admin_token))
    agent_token = _login(client, "agent1", "agentpass123")
    return admin_token, agent_token


def _register(client, username="alice", password="secret123", role="agent",
              token=None):
    headers = _bearer(token) if token else {}
    return client.post("/api/v1/auth/register",
                       json={"username": username, "password": password,
                             "role": role},
                       headers=headers)


class TestRegisterApi:
    def test_admin_can_register(self, client, db):
        """管理员建账号：成功，且新账号角色固定为 agent（服务端强制）。"""
        admin_token, _ = _seed_users(client, db)
        r = _register(client, username="alice", token=admin_token)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 200
        assert body["data"]["username"] == "alice"
        assert body["data"]["role"] == "agent"   # 服务层强制，防提权

    def test_anonymous_register_401(self, client, db):
        """匿名注册必须被拒（堵死自注册 admin 的提权路径）。"""
        r = _register(client)
        assert r.status_code == 401

    def test_agent_register_403(self, client, db):
        _, agent_token = _seed_users(client, db)
        r = _register(client, token=agent_token)
        assert r.status_code == 403

    def test_register_role_admin_still_agent(self, client, db):
        """即使请求体传 role=admin，落库也只能是 agent。"""
        admin_token, _ = _seed_users(client, db)
        r = _register(client, username="sneaky", role="admin",
                      token=admin_token)
        assert r.status_code == 200
        assert r.json()["data"]["role"] == "agent"

    def test_duplicate_409(self, client, db):
        admin_token, _ = _seed_users(client, db)
        _register(client, token=admin_token)
        r = _register(client, token=admin_token)
        assert r.status_code == 409           # 真实HTTP码必须透传（前端拦截器依赖）

    def test_short_password_422(self, client, db):
        admin_token, _ = _seed_users(client, db)
        r = _register(client, password="123", token=admin_token)  # schema 里 min_length=6
        assert r.status_code == 422


class TestLoginApi:
    def test_login_returns_token(self, client, db):
        _seed_users(client, db)
        r = client.post("/api/v1/auth/login",
                        data={"username": "agent1", "password": "agentpass123"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["access_token"]
        assert data["username"] == "agent1"   # 主界面顶部展示用

    def test_wrong_password_401(self, client, db):
        _seed_users(client, db)
        r = client.post("/api/v1/auth/login",
                        data={"username": "agent1", "password": "bad"})
        assert r.status_code == 401

    def test_rate_limit(self, client, db):
        """限流回归：第6次登录必须被限流 429。"""
        _seed_users(client, db)
        # seed 里的登录已消耗限流计数，这里归零后再数，保证 5+1 的口径干净
        from app.api.v1.endpoints.auth import limiter as auth_limiter
        auth_limiter.reset()
        codes = [client.post("/api/v1/auth/login",
                             data={"username": "agent1", "password": "bad"}).status_code
                 for _ in range(6)]
        assert codes[:5] == [401] * 5
        assert codes[5] == 429


class TestMeApi:
    def test_with_token(self, client, db):
        _seed_users(client, db)
        token = _login(client, "agent1", "agentpass123")
        r = client.get("/api/v1/auth/me", headers=_bearer(token))
        assert r.status_code == 200
        assert r.json()["data"]["username"] == "agent1"

    def test_without_token_401(self, client, db):
        assert client.get("/api/v1/auth/me").status_code == 401


class TestPermissionMatrix:
    """v1.1 安全加固回归：逐接口验权限口径，防将来改路由时权限回退。"""

    def test_kb_read_requires_login(self, client, db):
        assert client.get("/api/v1/kb").status_code == 401

    def test_kb_read_allows_staff(self, client, db):
        admin_token, agent_token = _seed_users(client, db)
        assert client.get("/api/v1/kb", headers=_bearer(admin_token)).status_code == 200
        assert client.get("/api/v1/kb", headers=_bearer(agent_token)).status_code == 200

    def test_kb_write_admin_only(self, client, db):
        _, agent_token = _seed_users(client, db)
        r = client.post("/api/v1/kb", json={"name": "x", "description": ""},
                        headers=_bearer(agent_token))
        assert r.status_code == 403
        assert client.delete("/api/v1/kb/documents/1",
                             headers=_bearer(agent_token)).status_code == 403

    def test_kb_public_is_anonymous(self, client, db):
        """访客端选库接口：匿名 200，但只暴露 id+name。"""
        r = client.get("/api/v1/kb/public")
        assert r.status_code == 200
        for item in r.json()["data"]:
            assert set(item.keys()) == {"id", "name"}

    def test_stats_admin_only(self, client, db):
        _, agent_token = _seed_users(client, db)
        assert client.get("/api/v1/stats/overview").status_code == 401
        assert client.get("/api/v1/stats/overview",
                          headers=_bearer(agent_token)).status_code == 403


class TestAgentWsAuth:
    """v1.1 安全加固回归：坐席 WebSocket 必须带本人 JWT。

    浏览器 WS 不能自定义请求头，令牌走 query；
    校验 sub==路径 user_id 且角色合法，否则门口 close(4401)。
    断言依据：connect_agent 只在鉴权通过后才把 user_id 登记进
    manager.agents，所以"在不在登记簿"就是过没过门口的铁证。
    """

    def _uid(self, client, token):
        return client.get("/api/v1/auth/me",
                          headers=_bearer(token)).json()["data"]["user_id"]

    def test_no_token_rejected(self, client, db):
        from app.services.ws_manager import manager
        admin_token, _ = _seed_users(client, db)
        uid = self._uid(client, admin_token)
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect(f"/api/v1/ws/agent/{uid}"):
                pass
        assert ei.value.code == 4401
        assert uid not in manager.agents

    def test_fake_token_rejected(self, client, db):
        from app.services.ws_manager import manager
        admin_token, _ = _seed_users(client, db)
        uid = self._uid(client, admin_token)
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect(
                    f"/api/v1/ws/agent/{uid}?token=fake.tok.en"):
                pass
        assert ei.value.code == 4401
        assert uid not in manager.agents

    def test_impersonate_other_id_rejected(self, client, db):
        from app.services.ws_manager import manager
        admin_token, _ = _seed_users(client, db)
        with pytest.raises(WebSocketDisconnect) as ei:
            with client.websocket_connect(
                    f"/api/v1/ws/agent/9999?token={admin_token}"):
                pass
        assert ei.value.code == 4401
        assert 9999 not in manager.agents

    def test_self_token_accepted(self, client, db):
        from app.services.ws_manager import manager
        _, agent_token = _seed_users(client, db)
        uid = self._uid(client, agent_token)
        with client.websocket_connect(
                f"/api/v1/ws/agent/{uid}?token={agent_token}"):
            assert uid in manager.agents   # 过了门口才会登记在线
