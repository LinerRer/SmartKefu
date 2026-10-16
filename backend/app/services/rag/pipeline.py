"""RAG 索引流水线与向量检索入口。

index_document: 分块 -> 批量embed -> 写Qdrant（id=chunk_id，幂等）
search_similar: 问题 -> 向量 -> Qdrant最近邻 -> 命中（含payload+score）
"""
from app.core.config import settings
from app.models.kb import Document, DocumentChunk
from app.services.rag.embeddings import embed_query, embed_texts
from app.services.rag.vector_store import delete_by_doc, ensure_collection, search_knn, upsert_points
from qdrant_client.models import PointStruct


def index_document(db, doc: Document) -> int:
    """给一篇已分块的文档建向量索引，返回写入点数。

    注意：bulk_insert_mappings 插的分块拿不到自增 id，
    所以这里回查 MySQL——这正是"MySQL 是 source of truth"的体现。
    """
    ensure_collection()
    rows = (db.query(DocumentChunk)
            .filter_by(doc_id=doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all())
    if not rows:
        return 0

    total = 0
    batch_size = settings.EMBED_BATCH_SIZE
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        vectors = embed_texts([r.content for r in batch])
        points = [
            PointStruct(
                id=chunk.id,  # point id = MySQL chunk_id
                vector=vec,
                payload={"chunk_id": chunk.id, "doc_id": doc.id,
                         "kb_id": doc.kb_id, "chunk_index": chunk.chunk_index},
            )
            for chunk, vec in zip(batch, vectors)
        ]
        upsert_points(points)
        total += len(points)
    return total


def reindex_document(db, doc: Document) -> int:
    """重建单篇索引：先删旧向量再写入。换 embedding 模型/调分块参数后用。"""
    delete_by_doc(doc.id)
    return index_document(db, doc)


def search_similar(query: str, kb_id: int | None = None, top_k: int = 5):
    """语义检索入口。返回命中点列表（score + payload），混合检索的向量一路。"""
    vector = embed_query(query)
    return search_knn(vector, kb_id=kb_id, top_k=top_k)


def get_chunk_contents(db, chunk_ids: list[int]) -> dict[int, str]:
    """命中后回 MySQL 取原文：{chunk_id: content}。"""
    if not chunk_ids:
        return {}
    rows = (db.query(DocumentChunk)
            .filter(DocumentChunk.id.in_(chunk_ids)).all())
    return {r.id: r.content for r in rows}