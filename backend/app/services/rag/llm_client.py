"""LLM 客户端：普通对话 / 流式对话 / 意图识别三出口。

走 openai SDK（DeepSeek 官方就是 OpenAI 兼容），与 embeddings.py 同款形态：
单例 + 配置驱动，换供应商只改这个文件。
"""
import json
import re

from openai import OpenAI

from app.core.config import settings
from app.core.logger import logger
from app.services.rag.prompts import INTENT_PROMPT, REWRITE_PROMPT

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
    return _client


def chat_completion(messages: list[dict]) -> str:
    """一次性完整回答。"""
    resp = _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=0.3,     # 客服场景：低温度=少发挥=多忠实资料
        max_tokens=400,
    )
    return resp.choices[0].message.content


def chat_stream(messages: list[dict]):
    """流式回答：yield 文本增量，SSE 接口的数据源。"""
    stream = _get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=400,
        stream=True,          # 关键参数：响应切成增量块返回
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


VALID_INTENTS = {"business", "chitchat", "human"}


def classify_intent(message: str) -> str:
    """意图识别，永远返回合法值——解析失败降级 business（安全默认）。"""
    raw = chat_completion([
        {"role": "user", "content": INTENT_PROMPT.format(message=message)}
    ])
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)   # 从围栏/闲话里抠出JSON
        intent = json.loads(m.group())["intent"] if m else None
    except (json.JSONDecodeError, KeyError, AttributeError):
        intent = None
    if intent not in VALID_INTENTS:
        logger.warning(f"意图解析失败，降级business。原文: {raw[:80]!r}")
        return "business"
    return intent


def rewrite_query(question: str, history: list[dict]) -> str:
    """查询改写（指代消解）：给检索用的独立问题。无历史直接原样返回。

    改写失败/结果异常 → 降级用原问题，绝不阻断主流程。
    """
    if not history:
        return question
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '客服'}：{m['content']}"
        for m in history[-6:]
    )
    try:
        out = chat_completion(
            [{"role": "user",
              "content": REWRITE_PROMPT.format(history=history_text,
                                               question=question)}]
        ).strip()
        if not out or len(out) > 100:      # 防跑偏：空/超长视为失败
            raise ValueError(f"改写结果异常: {out[:50]!r}")
        logger.info(f"查询改写: {question!r} -> {out!r}")
        return out
    except Exception as e:
        logger.warning(f"查询改写失败，用原问题: {e}")
        return question