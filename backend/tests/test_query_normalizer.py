# -*- coding: utf-8 -*-
"""查询归一化测试：缩写展开、长词优先、无误伤、空输入。"""
from app.services.rag.query_normalizer import normalize_query


class TestQueryNormalizer:
    def test_alias_expanded(self):
        assert normalize_query("计网是什么") == "计算机网络是什么"

    def test_multiple_aliases(self):
        out = normalize_query("计网的续航和降噪怎么样")
        assert "计算机网络" in out and "续航" in out and "降噪" in out

    def test_long_alias_priority(self):
        """长别名优先：'退换货政策' 整体映射，不被短词拆坏。"""
        assert normalize_query("退换货政策") == "退货政策"

    def test_no_alias_unchanged(self):
        """正路：无别名词原样返回，绝不误伤。"""
        assert normalize_query("你好") == "你好"
        assert normalize_query("今天天气") == "今天天气"

    def test_empty(self):
        assert normalize_query("") == ""
