"""Qdrant 向量库封装：全项目唯一允许直接操作 Qdrant 的模块。

三个纪律：
1. 模块级单例客户端——嵌入式模式同一目录同一时刻只能被一个进程打开（文件锁）；
2. 路径锚定 BACKEND_ROOT——不吃工作目录的脸色（相对路径曾导致数据分裂）；
3. 上层只调本模块函数，将来换 Milvus/云版 Qdrant 只改这一个文件。
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import BACKEND_ROOT, settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=str(BACKEND_ROOT / settings.QDRANT_LOCAL_PATH))
    return _client


def ensure_collection() -> None:
    """幂等建集合：已存在直接返回；首次创建时顺便建 payload 索引。"""
    client = get_client()
    if client.collection_exists(settings.QDRANT_COLLECTION):
        return
    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=VectorParams(
            size=settings.EMBEDDING_DIM, distance=Distance.COSINE
        ),
    )
    # kb_id/doc_id 建索引：每次检索都带过滤，没索引就是全库扫
    client.create_payload_index(
        collection_name=settings.QDRANT_COLLECTION,
        field_name="kb_id", field_schema="integer",
    )
    client.create_payload_index(
        collection_name=settings.QDRANT_COLLECTION,
        field_name="doc_id", field_schema="integer",
    )


def upsert_points(points: list[PointStruct]) -> None:
    """批量写入。point id 用 chunk_id：同 id 覆盖，重跑索引天然幂等。"""
    if points:
        get_client().upsert(
            collection_name=settings.QDRANT_COLLECTION, points=points
        )


def delete_by_doc(doc_id: int) -> None:
    """按 payload 过滤删除某文档的全部向量。"""
    get_client().delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="doc_id",
                                               match=MatchValue(value=doc_id))])
        ),
    )


def delete_by_kb(kb_id: int) -> None:
    """按 payload 过滤删除某知识库的全部向量（删库时一次性清理）。"""
    get_client().delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="kb_id",
                                               match=MatchValue(value=kb_id))])
        ),
    )


def search_knn(vector: list[float], kb_id: int | None = None, top_k: int = 5):
    """向量最近邻检索；kb_id 传 None 表示全库搜，传值则先过滤再搜。"""
    must = []
    if kb_id is not None:
        must.append(FieldCondition(key="kb_id", match=MatchValue(value=kb_id)))
    response = get_client().query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=Filter(must=must) if must else None,
        with_payload=True,
    )
    return response.points