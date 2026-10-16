"""WebSocket 实时通道：访客侧 / 坐席侧。协议见模块文档注释。

三条纪律：
1. 状态是路由真相源：人工模式下 AI 闭嘴，消息直转坐席；
2. 同步业务链走线程池（和 SSE 同款接缝），绝不直接卡事件循环；
3. 每条消息独立 Session：WS 是长连接，挂一个 session 会抽干连接池。
"""
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.chat_service import answer_message, record_message
from app.services.human_service import (
    agent_accept,
    leave_human,
    request_human,
    reset_idle_timer,
)
from app.services.ws_manager import manager

router = APIRouter()


def _push(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


@router.websocket("/visitor/{token}")
async def ws_visitor(websocket: WebSocket, token: str):
    db = SessionLocal()
    conv = db.query(Conversation).filter_by(visitor_token=token).first()
    db.close()
    if conv is None:
        await websocket.close(code=4404)     # 会话不存在：门口拒绝
        return
    await manager.connect_visitor(token, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue                     # 畸形包静默丢弃，不让一个坏包杀死整条连接
            await _handle_visitor(conv.id, msg, websocket)
    except WebSocketDisconnect:
        manager.disconnect_visitor(token)


async def _handle_visitor(conv_id: int, msg: dict, ws: WebSocket) -> None:
    db = SessionLocal()
    try:
        conv = db.get(Conversation, conv_id)
        kind = msg.get("type")
        if kind == "human":
            result = await request_human(db, conv)
            if result["accepted"]:
                reset_idle_timer(conv.id)   # 进入人工即开始 2 分钟计时
            await ws.send_text(_push({**result, "type": "human_result",
                                      "conversation_id": conv.id}))
        elif kind == "leave_human":
            ok = await leave_human(db, conv.id, "visitor")
            if not ok:
                await ws.send_text(_push({"type": "system", "text": "当前不在人工服务中"}))
        elif kind == "message":
            text = str(msg.get("text", ""))[:500]
            if not text:
                return
            if conv.status == Conversation.STATUS_HUMAN:
                reset_idle_timer(conv.id)   # 访客有新消息 → 超时重新计 2 分钟
                record_message(db, conv.id, Message.ROLE_VISITOR, text)
                await manager.send_to_agent(conv.agent_id, _push(
                    {"type": "visitor_message", "conversation_id": conv.id,
                     "text": text}))
            else:
                await _ai_reply(db, conv, text, ws)
    finally:
        db.close()


async def _ai_reply(db, conv: Conversation, text: str, ws: WebSocket) -> None:
    result = await run_in_threadpool(answer_message, db, conv, text)
    await ws.send_text(_push({"type": "ai_start",
                              "references": result.get("references", []),
                              "suggest_human": result["suggest_human"]}))
    if result["kind"] == "text":
        await ws.send_text(_push({"type": "ai_delta", "text": result["content"]}))
    else:
        async for piece in iterate_in_threadpool(result["generator"]):
            await ws.send_text(_push({"type": "ai_delta", "text": piece}))
    await ws.send_text(_push({"type": "ai_done"}))


@router.websocket("/agent/{user_id}")
async def ws_agent(websocket: WebSocket, user_id: int, token: str = Query("")):
    """坐席通道（v1.1 加固）：必须带本人 JWT，否则门口拒连。

    浏览器 WebSocket 无法自定义请求头，令牌走 query 参数；
    校验"令牌里的 sub 必须等于路径里的 user_id"，杜绝冒充其他坐席。
    """
    payload = verify_token(token) if token else None
    role = (payload or {}).get("role")
    if payload is None or int(payload.get("sub", -1)) != user_id \
            or role not in (User.ROLE_ADMIN, User.ROLE_AGENT):
        await websocket.close(code=4401)   # 未授权连接：门口拒绝
        return
    await manager.connect_agent(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await _handle_agent(user_id, msg, websocket)
    except WebSocketDisconnect:
        manager.disconnect_agent(user_id)
        # v1 已知限制：坐席掉线时正在处理的会话变成"孤儿"（status 卡在 human），
        # 在场管理和重新分配放后续迭代


async def _handle_agent(user_id: int, msg: dict, ws: WebSocket) -> None:
    db = SessionLocal()
    try:
        kind = msg.get("type")
        conv_id = msg.get("conversation_id")
        if kind == "accept":
            conv = await run_in_threadpool(agent_accept, db, user_id, conv_id)
            if conv is not None:
                reset_idle_timer(conv.id)   # 接管成功即开始 2 分钟计时
            await ws.send_text(_push({"type": "accept_result",
                                      "ok": conv is not None,
                                      "conversation_id": conv_id}))
        elif kind == "end":
            ok = await leave_human(db, conv_id, "agent")
            await ws.send_text(_push({"type": "end_result", "ok": ok,
                                      "conversation_id": conv_id}))
        elif kind == "message":
            conv = db.get(Conversation, conv_id) if conv_id else None
            if (conv is None or conv.agent_id != user_id
                    or conv.status != Conversation.STATUS_HUMAN):
                await ws.send_text(_push(
                    {"type": "error", "text": "无法发送：该会话未分配给你或不在人工模式"}))
                return
            text = str(msg.get("text", ""))[:500]
            record_message(db, conv.id, Message.ROLE_AGENT, text)
            await manager.send_to_visitor(conv.visitor_token, _push(
                {"type": "agent_message", "conversation_id": conv.id,
                 "text": text}))
    finally:
        db.close()