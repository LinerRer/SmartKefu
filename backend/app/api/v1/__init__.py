from fastapi import APIRouter

from app.api.v1.endpoints import agent, auth, chat, health, kb, stats, ws

api_router = APIRouter()
api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(auth.router, prefix="/auth", tags=["鉴权"])
api_router.include_router(kb.router, prefix="/kb", tags=["知识库"])
api_router.include_router(chat.router, prefix="/chat", tags=["对话"])
api_router.include_router(agent.router, prefix="/agent", tags=["坐席工作台"])
api_router.include_router(stats.router, prefix="/stats", tags=["数据看板"])
api_router.include_router(ws.router, prefix="/ws", tags=["实时通道"])