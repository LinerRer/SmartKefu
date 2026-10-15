import sys
from loguru import logger

from app.core.config import settings


def setup_logger():
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 控制台输出（彩色）
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
    )

    # 文件输出（每天轮转，保留 7 天）
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        level="INFO",
        format=log_format,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
    )
    return logger


setup_logger()
