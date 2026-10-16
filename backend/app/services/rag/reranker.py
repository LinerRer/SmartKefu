"""Rerank 客户端：交叉编码器精排。

与 embeddings.py 的关键差异：/v1/rerank 不在 OpenAI SDK 的覆盖面里
（SDK 没有 rerank 方法），所以用 httpx 直调 REST。
"OpenAI兼容"指的是 chat/embeddings 那套协议，不是整个 SDK 面。

响应形态（已核官方文档）：顶层 results 数组，元素 {index, relevance_score}，
已按分数降序；index 是传入 documents 的下标——原文不回传，省流量。
"""
import httpx

from app.core.config import settings
from app.core.logger import logger


def rerank(query: str, documents: list[str], top_n: int) -> list[dict]:
    """精排一批候选，返回 [{"index": 原下标, "relevance_score": 0~1}]（降序）。"""
    if not documents:
        return []
    api_key = settings.RERANK_API_KEY or settings.EMBEDDING_API_KEY
    resp = httpx.post(
        f"{settings.RERANK_BASE_URL}/rerank",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": settings.RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
        timeout=30,
    )
    resp.raise_for_status()      # 4xx/5xx 直接炸，不吞错误
    results = resp.json()["results"]
    logger.info(f"rerank {len(documents)} 条 -> top {len(results)}")
    return results