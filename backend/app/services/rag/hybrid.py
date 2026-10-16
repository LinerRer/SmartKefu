"""混合检索：向量路 + BM25路 -> RRF融合 -> Rerank精排 -> 阈值判定。

RRF 只认名次不认分数：向量cosine∈[0,1]、BM25分数无上界，量纲不同
不可直接相加；名次是两路唯一通用的语言。score(d)=Σ 1/(k+rank)。

v1 决策：kb_id 必传（会话必绑库，跨库检索是伪需求，砍掉省一半复杂度）。
"""
from app.core.config import settings
from app.core.logger import logger
from app.services.rag.bm25 import get_index
from app.services.rag.pipeline import get_chunk_contents, search_similar
from app.services.rag.query_normalizer import normalize_query
from app.services.rag.reranker import rerank


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """多路名次列表 -> 融合分降序 [(chunk_id, fused_score)]。"""
    fused: dict[int, float] = {}
    for one_rank in rankings:
        for rank, chunk_id in enumerate(one_rank, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


def search(db, query: str, kb_id: int, top_k: int | None = None) -> dict:
    """完整检索流水线。返回 hit / top1_score / candidates / trace。"""
    top_k = top_k or settings.RECALL_TOP_K
    # 查询归一化：缩写/口语展开成文档规范词（计网→计算机网络），提升字面与语义命中
    norm_query = normalize_query(query)
    if norm_query != query:
        logger.info(f"查询归一化: {query!r} -> {norm_query!r}")
    query = norm_query

    # —— 路1：向量（语义）——
    vec_hits = search_similar(query, kb_id=kb_id, top_k=top_k)
    vec_rank = [h.payload["chunk_id"] for h in vec_hits]
    vec_scores = {h.payload["chunk_id"]: h.score for h in vec_hits}

    # —— 路2：BM25（字面）——
    bm_hits = get_index(db, kb_id).search(query, top_k)
    bm_rank = [cid for cid, _ in bm_hits]
    bm_scores = dict(bm_hits)

    # —— RRF 融合（去重在 dict 里天然发生）——
    fused = rrf_fuse([vec_rank, bm_rank], k=settings.RRF_K)
    trace = {
        "vector": [{"chunk_id": c, "score": round(vec_scores[c], 4)} for c in vec_rank],
        "bm25": [{"chunk_id": c, "score": round(bm_scores[c], 4)} for c in bm_rank],
        "fused": [{"chunk_id": c, "rrf": round(s, 5)} for c, s in fused[:top_k]],
    }
    if not fused:
        return {"hit": False, "top1_score": 0.0, "candidates": [], "trace": trace}

    # —— 取融合前 top_k 回 MySQL 拿原文，进精排 ——
    cand_ids = [cid for cid, _ in fused[:top_k]]
    contents = get_chunk_contents(db, cand_ids)
    cand_ids = [cid for cid in cand_ids if cid in contents]   # 防御：向量残留
    cand_texts = [contents[cid] for cid in cand_ids]

    # —— Rerank 精排：返回的 index 是 cand_texts 的下标，必须翻译回 chunk_id ——
    ranked = rerank(query, cand_texts, settings.FINAL_TOP_N)
    rrf_map = dict(fused)
    final = []
    for r in ranked:
        cid = cand_ids[r["index"]]
        final.append({
            "chunk_id": cid,
            "score": r["relevance_score"],
            "rrf": round(rrf_map[cid], 5),
            "vec_score": round(vec_scores[cid], 4) if cid in vec_scores else None,
            "bm_score": round(bm_scores[cid], 4) if cid in bm_scores else None,
            "content": contents[cid],
        })

    top1 = final[0]["score"] if final else 0.0
    hit = top1 >= settings.RELEVANCE_THRESHOLD
    logger.info(f"hybrid检索 kb={kb_id} q={query[:20]!r} hit={hit} top1={top1:.4f}")
    return {"hit": hit, "top1_score": round(top1, 4), "candidates": final, "trace": trace}