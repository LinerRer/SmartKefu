"""对话服务：意图 → 检索 → Prompt → 流式 → 落库 → 未命中计数。

会话状态设计（v1）：
- 会话/消息落 MySQL（业务真相）；
- 连续未命中计数放内存 dict：会话级临时状态，重启即失，
  客服场景可接受（用户重连本就是新会话），后续可迁 Redis。
"""
import secrets

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import BusinessException
from app.core.logger import logger
from app.models.conversation import Conversation, Message
from app.models.kb import DocumentChunk
from app.services.rag import hybrid
from app.services.rag.llm_client import chat_stream, classify_intent, rewrite_query
from app.services.rag.prompts import (
    CHITCHAT_TEXT,
    FALLBACK_TEXT,
    HUMAN_TEXT,
    build_context,
    build_system,
)

_miss_counter: dict[int, int] = {}      # conversation_id -> 连续未命中次数


# ========== A段：会话与记忆 ==========

def create_conversation(db, kb_id: int) -> Conversation:
    """访客打开聊天窗口：建会话，发随机 token 当访客凭证。"""
    token = secrets.token_hex(16)       # 32位随机十六进制，不可猜测
    conv = Conversation(visitor_token=token, kb_id=kb_id,
                        status=Conversation.STATUS_AI)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_conversation(db, token: str) -> Conversation:
    conv = db.query(Conversation).filter_by(visitor_token=token).first()
    if not conv:
        raise BusinessException(code=404, message="会话不存在或已结束")
    return conv


def get_history(db, conversation_id: int) -> list[dict]:
    """滑动窗口记忆：取最近 N 轮（一问一答=2条），转成 OpenAI 消息格式。"""
    rows = (db.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.id.desc())
            .limit(settings.MAX_HISTORY_TURNS * 2)
            .all())
    return [{"role": "assistant" if r.role == Message.ROLE_AI else "user",
             "content": r.content}
            for r in reversed(rows)]


def _save_message(db, conversation_id: int, role: str, content: str,
                  references=None) -> Message:
    msg = Message(conversation_id=conversation_id, role=role,
                  content=content, references=references)
    db.add(msg)
    db.commit()
    return msg


def _miss_response(db, conv: Conversation) -> dict:
    """未命中的统一出口：计数+1，达阈值在话术里追加转人工建议。"""
    miss = _miss_counter.get(conv.id, 0) + 1
    _miss_counter[conv.id] = miss
    suggest = miss >= settings.MISS_TO_HUMAN_THRESHOLD
    content = FALLBACK_TEXT + ("，需要的话我可以帮您转接人工客服～" if suggest else "")
    _save_message(db, conv.id, Message.ROLE_AI, content)
    logger.info(f"会话={conv.id} 未命中 计数={miss} suggest_human={suggest}")
    return {"kind": "text", "content": content, "suggest_human": suggest}


# ========== B段：答案编排 ==========

def answer_message(db, conv: Conversation, question: str) -> dict:
    """处理一条访客消息。返回：
    kind="text"   → content 固定话术（已落库）
    kind="stream" → generator 增量文本（消费完自动落库）+ references
    """
    _save_message(db, conv.id, Message.ROLE_VISITOR, question)
    intent = classify_intent(question)
    logger.info(f"会话={conv.id} intent={intent}")

    if intent == "human":
        _save_message(db, conv.id, Message.ROLE_AI, HUMAN_TEXT)
        return {"kind": "text", "content": HUMAN_TEXT, "suggest_human": True}

    if intent == "chitchat":
        _save_message(db, conv.id, Message.ROLE_AI, CHITCHAT_TEXT)
        return {"kind": "text", "content": CHITCHAT_TEXT, "suggest_human": False}

    # business / out_of_scope 都走检索：LLM 不知道 KB 里有什么，
    # 不能由它预判"超出范围"而跳过检索；检索的 reranker 阈值才是命中判据。
    history = get_history(db, conv.id)          # 含刚存的当前问题
    query = rewrite_query(question, history[:-1]) if len(history) > 1 else question
    result = hybrid.search(db, query, kb_id=conv.kb_id)
    if not result["hit"]:
        return _miss_response(db, conv)

    _miss_counter[conv.id] = 0          # 命中即清零
    candidates = result["candidates"]

    # references：补 doc_id，前端"展开来源"要用
    chunk_ids = [c["chunk_id"] for c in candidates]
    chunk_map = {c.id: c for c in
                 db.query(DocumentChunk)
                 .filter(DocumentChunk.id.in_(chunk_ids)).all()}
    references = [{"chunk_id": c["chunk_id"],
                   "doc_id": chunk_map[c["chunk_id"]].doc_id,
                   "score": c["score"],
                   "snippet": c["content"][:80]}
                  for c in candidates]

    # 消息数组 = system + 历史（刚存的当前问题就在历史最后一条）
    messages = [{"role": "system",
                 "content": build_system(build_context(candidates))}]
    messages += history

    def stream_and_persist():
        parts = []
        for piece in chat_stream(messages):
            parts.append(piece)
            yield piece
        # ★ 流消费完时，请求的会话可能已关闭——落库自开一个 session
        db2 = SessionLocal()
        try:
            _save_message(db2, conv.id, Message.ROLE_AI, "".join(parts),
                          references=references)
        finally:
            db2.close()

    return {"kind": "stream", "generator": stream_and_persist(),
            "references": references, "suggest_human": False}


def record_message(db, conversation_id: int, role: str, content: str,
                   references=None) -> Message:
    """消息落库公开入口（WS 人工通道用；人工对话也要记日志，H-05 历史查看要靠它）。"""
    return _save_message(db, conversation_id, role, content, references)