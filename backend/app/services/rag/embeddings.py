"""Embedding 客户端：把文本变成向量。

只暴露两个动作：批量 embed、单条 embed_query。
换平台（硅基流动 -> Ollama 私有化）时只动这一个文件，上层无感知。
"""
from openai import OpenAI

from app.core.config import settings
from app.core.logger import logger

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    """模块级单例：一个进程共用一个连接池，重复建 client 浪费 TCP/TLS 握手。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，返回顺序与输入一致。空列表直接返回，不发废请求。"""
    if not texts:
        return []
    client = _get_client()
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    # 防御性校验：平台异常时可能少回一条，宁可炸也不能错位入库
    if len(response.data) != len(texts):
        raise RuntimeError(
            f"embedding 返回数量不符: 期望{len(texts)} 实际{len(response.data)}"
        )
    vectors = [item.embedding for item in response.data]
    logger.info(f"embed {len(texts)} 条 -> {len(vectors[0])} 维")
    return vectors


def embed_query(text: str) -> list[float]:
    """查询专用入口：内部复用批量接口（单条也是合法的批量）。"""
    return embed_texts([text])[0]