"""统计服务：所有看板指标的计算口径集中在这一个文件。

口径原则：转人工/AI解决从 messages 事件流判定，不依赖 status 快照
（退出人工会把 status 改回 ai，快照会丢历史事实）。
"""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message

# 子查询：每个会话是否有 agent 消息 / ai 消息（事件流判定）
_has_agent = func.sum(func.if_(Message.role == "agent", 1, 0)).label("n_agent")
_has_ai = func.sum(func.if_(Message.role == "ai", 1, 0)).label("n_ai")

def _msg_flags(db: Session):
    return (db.query(Message.conversation_id, _has_agent, _has_ai)
            .group_by(Message.conversation_id).subquery())

def overview(db: Session) -> dict:
    """总览四数字：总会话、转人工率、AI解决率、平均满意度。"""
    flags = _msg_flags(db)
    total = db.query(func.count(Conversation.id)).scalar() or 0
    row = (db.query(
                func.sum(func.if_(flags.c.n_agent > 0, 1, 0)),
                func.sum(func.if_((flags.c.n_agent == 0) & (flags.c.n_ai > 0), 1, 0)))
           .select_from(Conversation).outerjoin(flags, flags.c.conversation_id == Conversation.id)
           .one())
    to_human, ai_solved = int(row[0] or 0), int(row[1] or 0)
    from app.models.ticket import Feedback
    avg_rating = (db.query(func.avg(Feedback.rating)).scalar())
    return {
        "total_conversations": total,
        "to_human_count": to_human,
        "to_human_rate": round(to_human / total, 4) if total else 0,
        "ai_solved_count": ai_solved,
        "ai_solved_rate": round(ai_solved / total, 4) if total else 0,
        "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
    }

def daily_trend(db: Session, days: int = 14) -> list[dict]:
    """近 N 天：每日会话量 + 每日转人工数。"""
    since = datetime.now() - timedelta(days=days)
    flags = _msg_flags(db)
    day = func.date(Conversation.created_at).label("d")
    rows = (db.query(day,
                    func.count(Conversation.id),
                    func.sum(func.if_(flags.c.n_agent > 0, 1, 0)))
            .select_from(Conversation)
            .outerjoin(flags, flags.c.conversation_id == Conversation.id)
            .filter(Conversation.created_at >= since)
            .group_by(day).order_by(day).all())
    return [{"date": str(r[0]), "conversations": r[1], "to_human": int(r[2] or 0)} for r in rows]

def hot_questions(db: Session, top_n: int = 10) -> list[dict]:
    """热门问题 Top：visitor 消息字面频次（v1 不做语义归一）。"""
    rows = (db.query(Message.content, func.count(Message.id))
            .filter(Message.role == "visitor")
            .group_by(Message.content)
            .order_by(func.count(Message.id).desc()).limit(top_n).all())
    return [{"question": r[0][:50], "count": r[1]} for r in rows]

def first_response_seconds(db: Session, sample_limit: int = 200) -> float | None:
    """首响时长：每会话 首条ai时间 - 首条visitor时间 的均值。"""
    conv_ids = (db.query(Conversation.id)
                .order_by(Conversation.id.desc()).limit(sample_limit).all())
    diffs = []
    for (cid,) in conv_ids:
        first_v = (db.query(Message.created_at)
                   .filter_by(conversation_id=cid, role="visitor")
                   .order_by(Message.id).first())
        first_a = (db.query(Message.created_at)
                   .filter_by(conversation_id=cid, role="ai")
                   .order_by(Message.id).first())
        if first_v and first_a and first_a[0] >= first_v[0]:
            diffs.append((first_a[0] - first_v[0]).total_seconds())
    return round(sum(diffs) / len(diffs), 1) if diffs else None