"""坐席工作台路由：排队队列、我的会话、会话历史（HTTP 只读查询）。

接管与实时收发走 WS（ws.py），这里只给前端提供"打开页面时先拉一遍现状"的接口。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.common import ResponseSchema, success
from app.api.v1.deps import require_role
from app.models.user import User
from app.services.human_service import human_queue

router = APIRouter()

# 队列/会话是坐席与管理视角的数据，访客 token 拿不到
guard = require_role(User.ROLE_ADMIN, User.ROLE_AGENT)


@router.get("/queue", response_model=ResponseSchema, summary="转人工排队队列")
def get_queue(db: Session = Depends(get_db), user: User = Depends(guard)):
    rows = db.query(Conversation).filter(
        Conversation.id.in_(list(human_queue))).all()
    items = [{"conversation_id": c.id, "kb_id": c.kb_id,
              "created_at": str(c.created_at)} for c in rows]
    return success(data=items)


@router.get("/conversations", response_model=ResponseSchema, summary="我接管的会话列表")
def my_conversations(db: Session = Depends(get_db), user: User = Depends(guard)):
    rows = (db.query(Conversation)
            .filter_by(agent_id=user.id, status=Conversation.STATUS_HUMAN)
            .order_by(Conversation.id.desc()).all())
    items = [{"conversation_id": c.id, "kb_id": c.kb_id,
              "status": c.status} for c in rows]
    return success(data=items)


@router.get("/conversations/{conv_id}/messages", response_model=ResponseSchema,
            summary="会话历史消息")
def conversation_messages(conv_id: int, db: Session = Depends(get_db),
                          user: User = Depends(guard)):
    rows = (db.query(Message).filter_by(conversation_id=conv_id)
            .order_by(Message.id).all())
    items = [{"id": m.id, "role": m.role, "content": m.content,
              "references": m.references} for m in rows]
    return success(data=items)
