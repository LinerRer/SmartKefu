"""BM25 关键词检索：混合检索的第二路。

向量路按"意思"找，BM25 按"字面词"找，失败模式互补。
中文前提：BM25 假设输入是词，必须先 jieba 分词。

索引生命周期（v1 取舍，面试要能讲）：
- 纯内存索引，按 kb_id 缓存；服务重启即失，首次用到时从 MySQL 全量重建；
- 文档增删调 invalidate(kb_id) 作废旧缓存；
- 不做增量维护：几百个分块全量重建只要毫秒级，规模大了再还这笔技术债。
"""
import jieba

_cache: dict[int, "Bm25Index"] = {}


def tokenize(text: str) -> list[str]:
    """分词 + 小写（英文型号大小写不敏感）+ 去掉纯空白词。"""
    return [w.lower() for w in jieba.lcut(text) if w.strip()]


class Bm25Index:
    """一个知识库一套 BM25 索引：语料（分好词的块列表）+ 打分器。"""

    def __init__(self, chunk_ids: list[int], texts: list[str]):
        from rank_bm25 import BM25Okapi

        self.chunk_ids = chunk_ids
        self.corpus_tokens = [tokenize(t) for t in texts]
        self.scorer = BM25Okapi(self.corpus_tokens)


    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """返回 [(chunk_id, 分数)] 降序。

        注意：单文档知识库时 BM25Okapi 的 IDF 可能为负（N=1,n=1），
        不能用 >0 过滤——RRF 融合只用排名不用绝对分数，负分不影响排序。
        查询词全不命中时分数全为 0，调用方通过空列表或全 0 自行判断。
        """
        scores = self.scorer.get_scores(tokenize(query))
        order = sorted(range(len(scores)),
                       key=lambda i: scores[i], reverse=True)
        return [(self.chunk_ids[i], float(scores[i]))
                for i in order[:top_k]]


def get_index(db, kb_id: int) -> Bm25Index:
    """惰性建索引：缓存命中直接返回，否则从 MySQL 拉该库全部分块重建。"""
    if kb_id not in _cache:
        from app.models.kb import DocumentChunk

        rows = (db.query(DocumentChunk)
                .filter_by(kb_id=kb_id)
                .order_by(DocumentChunk.id)
                .all())
        _cache[kb_id] = Bm25Index([r.id for r in rows],
                                  [r.content for r in rows])
    return _cache[kb_id]


def invalidate(kb_id: int) -> None:
    """文档增删后调用：作废旧索引，下次检索时重建。"""
    _cache.pop(kb_id, None)