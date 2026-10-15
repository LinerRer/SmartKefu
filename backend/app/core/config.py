from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# backend 根目录（config.py 在 backend/app/core/ 下，向上三层）
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


    # 应用配置
    APP_NAME: str = "SmartKefu"
    DEBUG: bool = True


    # 服务器配置
    HOST: str = "127.0.0.1"
    PORT: int = 8000


    #数据库配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "smart_kefu"


    # 大模型配置
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"


    # RAG 分块参数（检索测试时调优）
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80


    # Embedding：OpenAI兼容协议调用 bge-m3
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    EMBED_BATCH_SIZE: int = 32

    # Qdrant：本地嵌入式数据目录
    QDRANT_LOCAL_PATH: str = "data/qdrant"
    QDRANT_COLLECTION: str = "kb_chunks"


    # Rerank：硅基流动 /v1/rerank（非OpenAI协议，httpx直调）
    RERANK_API_KEY: str = ""          # 留空则复用 EMBEDDING_API_KEY（同平台同Key）
    RERANK_BASE_URL: str = "https://api.siliconflow.cn/v1"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"


    # 混合检索参数（初始值是猜测，评测调出实证值）
    RECALL_TOP_K: int = 20            # 每路召回数
    RRF_K: int = 60                   # RRF 平滑常数
    FINAL_TOP_N: int = 4              # 精排后进入上下文的条数
    RELEVANCE_THRESHOLD: float = 0.3  # 相关度阈值（评测集校准得出）


    # 对话
    MAX_HISTORY_TURNS: int = 5        # 滑动窗口轮数（一问一答为一轮）
    MISS_TO_HUMAN_THRESHOLD: int = 2  # 连续未命中N次 → 建议转人工


    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"   # 生产必须改，.env 注入
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Redis（可选）
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = False                        # 没装 Redis 就 False


    # 初始化管理员账号（仅 init_admin.py 使用，密码必须由 .env 注入）
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""


    @field_validator("DB_PASSWORD")
    @classmethod
    def password_required(cls, v: str) -> str:
        if not v:
            raise ValueError("DB_PASSWORD 未配置：请在 backend/.env 中设置")
        return v


settings = Settings()