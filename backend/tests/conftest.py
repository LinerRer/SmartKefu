# -*- coding: utf-8 -*-
"""pytest 共享夹具：测试库隔离 + 应用测试客户端。

隔离策略：连同一 MySQL 实例上的 smart_kefu_test 库（同引擎，
才能测到 func.if_/JSON 列这些 MySQL 特有行为；SQLite 会假通过）。

fixture 生命周期：
- db：每个测试用例函数一个独立 Session（用例间数据互不污染，靠 rollback）
- 建表/清表放在 session 级：整个测试会话开头 create_all、结尾 drop_all
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.base import Base
from app.models import user, kb, conversation, ticket  # noqa: F401  (确保模型注册进 metadata)

TEST_DB_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/smart_kefu_test?charset=utf8mb4"
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, poolclass=NullPool)
    Base.metadata.create_all(eng)      # 用模型定义建表：测试 schema 永远与代码同步
    yield eng
    Base.metadata.drop_all(eng)        # 收尾清库，不留脏数据


@pytest.fixture
def db(engine):
    """每用例独立 Session，前后清空所有表。

    注意不能只靠 rollback：被测代码（如 register_user）自己会 commit，
    提交过的数据 rollback 撤不掉，所以显式清表。
    """
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with engine.begin() as conn:          # 2.0 风格：execute 只在 Connection 上
        for t in reversed(Base.metadata.sorted_tables):
            conn.execute(t.delete())
    session = Session()
    yield session
    session.close()
