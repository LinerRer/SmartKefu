"""对话路由：创建会话 + SSE 流式问答。

SSE 事件协议（前端按 event 名分发）：
  meta  {"kind","references","suggest_human"}  ← 先告诉你答案形态和引用
  delta {"text": "..."}                        ← 增量文本，来 N 次
  done  {}                                     ← 结束哨兵
"""
import json

from fastapi import APIRouter, Depends
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.schemas.chat import ChatBody, ConversationCreate
from app.schemas.common import ResponseSchema, success
from app.services.chat_service import (
    answer_message,
    create_conversation,
    get_conversation,
)

router = APIRouter()


@router.post("/conversations", response_model=ResponseSchema, summary="创建会话")
def new_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    conv = create_conversation(db, body.kb_id)
    return success(data={"conversation_token": conv.visitor_token})


@router.post("/messages", summary="发送消息（SSE 流式回答）")
async def chat_message(body: ChatBody, db: Session = Depends(get_db)):
    conv = get_conversation(db, body.token)
    # 同步业务链扔线程池：意图+检索要等一两秒，别卡事件循环
    result = await run_in_threadpool(answer_message, db, conv, body.question)

    async def event_gen():
        yield {"event": "meta", "data": json.dumps(
            {"kind": result["kind"],
             "references": result.get("references", []),
             "suggest_human": result["suggest_human"]},
            ensure_ascii=False)}
        if result["kind"] == "text":
            yield {"event": "delta", "data": json.dumps(
                {"text": result["content"]}, ensure_ascii=False)}
        else:
            async for piece in iterate_in_threadpool(result["generator"]):
                yield {"event": "delta", "data": json.dumps(
                    {"text": piece}, ensure_ascii=False)}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_gen())
