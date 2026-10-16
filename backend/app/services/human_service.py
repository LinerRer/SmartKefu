"""转人工服务：会话状态机 + 排队队列 + 坐席接管 + 退出人工。

状态机（conversations.status）：
    ai    -> human   AI 交棒给人工坐席
    ai    -> closed  访客直接离开
    human -> ai      退出人工（访客主动/坐席结束/2分钟超时），回到 AI 服务
    human -> closed  人工处理完关单
其余流转一律抛 IllegalTransitionError。
"""
import asyncio
import json
from collections import deque

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.database import SessionLocal
from app.models.conversation import Conversation
from app.services.ws_manager import manager

ALLOWED = {
    "ai": {"human", "closed"},
    "human": {"ai", "closed"},
    "closed": set(),
}

human_queue: deque[int] = deque()   # 排队等待接管的会话 id

IDLE_TIMEOUT_SECONDS = 120          # 人工模式下访客 2 分钟无新消息 → 自动退出
idle_timers: dict[int, asyncio.TimerHandle] = {}   # conv_id -> 定时器句柄


class IllegalTransitionError(Exception):
    """非法的状态流转。"""


def _push(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def change_status(db: Session, conv: Conversation, new: str,
                  agent_id: int | None = None) -> None:
    old = conv.status
    if new not in ALLOWED.get(old, set()):
        raise IllegalTransitionError(f"会话 {conv.id}: {old} -> {new} 非法流转")
    conv.status = new
    if agent_id is not None:
        conv.agent_id = agent_id
    db.commit()
    logger.info(f"会话 {conv.id} 状态: {old} -> {new}")


async def request_human(db: Session, conv: Conversation) -> dict:
    """转人工入口：有在线坐席立即接管，没有则排队。"""
    if conv.status == "human":
        return {"accepted": True, "agent_id": conv.agent_id, "queued": False}
    if conv.status == "closed":
        return {"accepted": False, "agent_id": None, "queued": False}

    agent_id = next(iter(manager.agents), None)
    if agent_id is not None:
        change_status(db, conv, "human", agent_id=agent_id)
        await manager.send_to_visitor(conv.visitor_token, _push(
            {"type": "system", "text": "已为您接入人工客服"}))
        await manager.send_to_agent(agent_id, _push(
            {"type": "system", "text": f"您已接管会话 {conv.id}",
             "conversation_id": conv.id}))
        return {"accepted": True, "agent_id": agent_id, "queued": False}

    if conv.id not in human_queue:
        human_queue.append(conv.id)
    await manager.send_to_visitor(conv.visitor_token, _push(
        {"type": "system", "text": "暂无客服在线，已为您排队，请稍候"}))
    logger.info(f"会话 {conv.id} 进入转人工队列，队列长度 {len(human_queue)}")
    return {"accepted": False, "agent_id": None, "queued": True}


async def agent_accept(db: Session, agent_id: int, conv_id: int) -> Conversation | None:
    """坐席主动接管一个排队中的会话。"""
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.status != "ai":
        return None
    if conv.id in human_queue:
        human_queue.remove(conv.id)
    change_status(db, conv, "human", agent_id=agent_id)
    await manager.send_to_visitor(conv.visitor_token, _push(
        {"type": "system", "text": "已为您接入人工客服"}))
    return conv


# ===== 退出人工：访客主动 / 坐席结束 / 超时自动，三条路同一个收口 =====

async def leave_human(db: Session, conv_id: int, reason: str) -> bool:
    """human -> ai：停计时、通知访客端、清坐席绑定标记。

    reason: "visitor" 访客退出 | "agent" 坐席结束 | "timeout" 超时自动
    """
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.status != Conversation.STATUS_HUMAN:
        return False
    cancel_idle_timer(conv.id)
    change_status(db, conv, "ai")
    conv.agent_id = None
    db.commit()
    text = {
        "visitor": "您已退出人工客服，已切换回 AI 助手为您服务。",
        "agent": "人工客服已结束本次服务，已切换回 AI 助手为您服务。",
        "timeout": "超过 2 分钟未收到您的消息，已自动切换回 AI 助手。如有问题可继续提问。",
    }[reason]
    await manager.send_to_visitor(conv.visitor_token, _push(
        {"type": "human_closed", "reason": reason, "text": text}))
    # 广播给在线坐席刷新会话列表（v1 简化：不单独寻址原坐席）
    await manager.broadcast_to_agents(_push(
        {"type": "conversation_closed", "conversation_id": conv.id,
         "text": f"会话 {conv.id} 已退出人工（{reason}）"}))
    logger.info(f"会话 {conv.id} 退出人工，原因={reason}")
    return True


def reset_idle_timer(conv_id: int) -> None:
    """访客每发一条消息调用：重置 2 分钟超时计时。"""

    def _fire():
        asyncio.create_task(_timeout_leave(conv_id))

    cancel_idle_timer(conv_id)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # 不在事件循环里（如单测直接调用），跳过计时
    idle_timers[conv_id] = loop.call_later(IDLE_TIMEOUT_SECONDS, _fire)


def cancel_idle_timer(conv_id: int) -> None:
    handle = idle_timers.pop(conv_id, None)
    if handle is not None:
        handle.cancel()


async def _timeout_leave(conv_id: int) -> None:
    """定时器到期：重查状态再退出，防止期间已被人工方式退出导致重复操作。"""
    idle_timers.pop(conv_id, None)
    db = SessionLocal()
    try:
        await leave_human(db, conv_id, "timeout")
    finally:
        db.close()