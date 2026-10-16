from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.logger import logger
from app.schemas.common import ResponseSchema, success
from app.core.exceptions import register_exception
from app.api.v1 import api_router
from app.services.daily_report import run_daily_job

# 配置限流器
limiter = Limiter(key_func=get_remote_address)

# 日报调度器：进程内后台线程，每天 01:00 生成昨日日报
scheduler = BackgroundScheduler()
scheduler.add_job(run_daily_job, "cron", hour=1, minute=0, id="daily_report")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    logger.info("SmartKefu 服务启动成功（日报调度已挂载，每天 01:00）")
    yield
    scheduler.shutdown(wait=False)
    logger.info("SmartKefu 服务已关闭")


app = FastAPI(title="SmartKefu", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception(app)
app.include_router(api_router, prefix="/api/v1")

@app.get("/", response_model=ResponseSchema)
def root():
    logger.info("收到根路径请求")
    return success(data={"message": "Hello SmartKefu"})


@app.get("/test-error", response_model=ResponseSchema)
def test_error():
    from app.core.exceptions import BusinessException
    raise BusinessException(code=400, message="这是一条业务测试报错")
