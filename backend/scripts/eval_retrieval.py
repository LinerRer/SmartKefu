"""检索评测：四配置对比 Hit@4。

配置：vector_only / bm25_only / hybrid(RRF) / hybrid+rerank
判定：top4 块中任一块含 expect_kw 即命中（Hit Rate@4）
负例：只有 hybrid+rerank 有 hit 判定，其余配置 N/A
前提：语料候选空间足够大（几十块以上），否则全员满分、评测无意义。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.kb import KnowledgeBase
from app.services.rag import hybrid
from app.services.rag.bm25 import get_index
from app.services.rag.pipeline import get_chunk_contents, search_similar
from app.services.rag.vector_store import get_client
from app.core.config import settings

TOP_N = settings.FINAL_TOP_N          # 4，与线上口径一致
db = SessionLocal()
kb = db.query(KnowledgeBase).filter_by(name="BM25测试").first()
items = json.loads(Path("eval/retrieval_eval.json").read_text(encoding="utf-8"))


def hit_check(chunk_ids: list[int], expect_kw: str) -> bool:
    """top4 里任一块原文含关键词即算命中。"""
    contents = get_chunk_contents(db, chunk_ids)
    return any(expect_kw in contents.get(cid, "") for cid in chunk_ids)


def run_config(name: str, item: dict) -> bool:
    q, kw = item["q"], item["expect_kw"]
    if name == "vector_only":
        ids = [h.payload["chunk_id"] for h in search_similar(q, kb_id=kb.id, top_k=TOP_N)]
        return hit_check(ids, kw)
    if name == "bm25_only":
        ids = [cid for cid, _ in get_index(db, kb.id).search(q, TOP_N)]
        return hit_check(ids, kw)
    if name == "hybrid":
        vec = [h.payload["chunk_id"] for h in search_similar(q, kb_id=kb.id,
                                                             top_k=settings.RECALL_TOP_K)]
        bm = [cid for cid, _ in get_index(db, kb.id).search(q, settings.RECALL_TOP_K)]
        fused = hybrid.rrf_fuse([vec, bm], k=settings.RRF_K)
        return hit_check([cid for cid, _ in fused[:TOP_N]], kw)
    if name == "hybrid+rerank":
        result = hybrid.search(db, q, kb_id=kb.id)
        return any(kw in c["content"] for c in result["candidates"])
    raise ValueError(name)


CONFIGS = ["vector_only", "bm25_only", "hybrid", "hybrid+rerank"]
pos_items = [it for it in items if it.get("expect_kw")]
neg_items = [it for it in items if not it.get("expect_kw")]

print(f"评测集: {len(pos_items)} 正例 + {len(neg_items)} 负例 | 库 kb={kb.id}\n")
header = f"{'配置':<16}{'Hit@4':>10}{'耗时/问':>10}"
print(header); print("-" * 28)
for cfg in CONFIGS:
    t0 = time.time()
    hits = sum(1 for it in pos_items if run_config(cfg, it))
    rate = hits / len(pos_items) * 100
    avg = (time.time() - t0) / len(pos_items)
    print(f"{cfg:<16}{hits}/{len(pos_items)} = {rate:4.0f}%{avg:>8.2f}s")

# 负例：只有带阈值的完整流水线能判
print()
for it in neg_items:
    r = hybrid.search(db, it["q"], kb_id=kb.id)
    print(f"负例 '{it['q']}': top1={r['top1_score']} hit={r['hit']}（预期 False）")

db.close()
get_client().close()
print("\n评测完成——对比表可存档，作为检索效果的量化依据")