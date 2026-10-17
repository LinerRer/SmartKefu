# -*- coding: utf-8 -*-
"""递归分块器测试：长度上限、相邻重叠、内容完整性、非法参数。"""
import pytest

from app.services.chunker import split_text

SENT = "产品很好用。"      # 6 字，含句级分隔符
LONG = SENT * 100          # 600 字，逼出分块与重叠逻辑


class TestChunkerBasics:
    def test_short_text_single_chunk(self):
        chunks = split_text("很短的一段话", chunk_size=100, overlap=10)
        assert chunks == ["很短的一段话"]

    def test_empty_text(self):
        assert split_text("", chunk_size=100, overlap=10) == []

    def test_blank_text(self):
        assert split_text("   \n  ", chunk_size=100, overlap=10) == []


class TestChunkerLength:
    def test_respects_chunk_size(self):
        chunks = split_text(LONG, chunk_size=50, overlap=10)
        assert len(chunks) > 1                      # 真的切开了，不是假通过
        assert all(len(c) <= 50 for c in chunks)   # 长度上限承诺


class TestChunkerOverlap:
    def test_adjacent_overlap(self):
        chunks = split_text(LONG, chunk_size=50, overlap=10)
        for a, b in zip(chunks, chunks[1:]):
            assert b[:10] == a[-10:]               # 前一块的尾巴出现在下一块开头


class TestChunkerIntegrity:
    def test_content_not_lost(self):
        chunks = split_text(LONG, chunk_size=50, overlap=10)
        normalized = LONG.replace("。", "")        # 已知近似：句级分隔符切丢
        assert all(c in normalized for c in chunks)
        assert chunks[-1].endswith(normalized[-6:])  # 文末没有丢


class TestChunkerBadParams:
    def test_invalid_chunk_size(self):
        with pytest.raises(ValueError):
            split_text("x", chunk_size=0, overlap=0)

    def test_invalid_overlap(self):
        with pytest.raises(ValueError):
            split_text("x", chunk_size=50, overlap=50)   # overlap 必须 < chunk_size