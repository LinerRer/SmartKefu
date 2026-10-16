from fastapi import WebSocket

from app.core.logger import logger


class ConnectionManager:
    """进程内连接总机：登记访客/坐席的 WS 连接，支持定向与广播发送。"""

    def __init__(self):
        self.visitors: dict[str, WebSocket] = {}   # visitor_token -> 连接
        self.agents: dict[int, WebSocket] = {}     # user_id -> 连接

    async def connect_visitor(self, token: str, ws: WebSocket) -> None:
        await ws.accept()
        self.visitors[token] = ws
        logger.info(f"访客 {token} 已连接，当前访客数 {len(self.visitors)}")

    async def connect_agent(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.agents[user_id] = ws
        logger.info(f"坐席 {user_id} 已连接，当前坐席数 {len(self.agents)}")

    def disconnect_visitor(self, token: str) -> None:
        self.visitors.pop(token, None)
        logger.info(f"访客 {token} 已断开，当前访客数 {len(self.visitors)}")

    def disconnect_agent(self, user_id: int) -> None:
        self.agents.pop(user_id, None)
        logger.info(f"坐席 {user_id} 已断开，当前坐席数 {len(self.agents)}")

    async def send_to_visitor(self, token: str, text: str) -> bool:
        ws = self.visitors.get(token)
        if ws is None:
            return False
        await ws.send_text(text)
        return True

    async def send_to_agent(self, user_id: int, text: str) -> bool:
        ws = self.agents.get(user_id)
        if ws is None:
            return False
        await ws.send_text(text)
        return True

    async def broadcast_to_agents(self, text: str) -> int:
        count = 0
        for ws in list(self.agents.values()):
            await ws.send_text(text)
            count += 1
        return count

    def online_agent_count(self) -> int:
        return len(self.agents)


manager = ConnectionManager()