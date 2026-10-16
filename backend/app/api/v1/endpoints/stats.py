"""看板路由：只做 HTTP 的事——收参数、调 stats_service、包响应。

权限约定（v1.1 安全加固）：看板是经营数据，仅 admin 可见。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ResponseSchema, success
from app.services import stats_service

router = APIRouter()

admin_guard = require_role(User.ROLE_ADMIN)


@router.get("/overview", response_model=ResponseSchema, summary="总览指标")
def overview(db: Session = Depends(get_db), user: User = Depends(admin_guard)):
    data = stats_service.overview(db)
    data["first_response_seconds"] = stats_service.first_response_seconds(db)
    return success(data=data)


@router.get("/daily-trend", response_model=ResponseSchema, summary="每日趋势")
def daily_trend(db: Session = Depends(get_db), days: int = Query(14, ge=1, le=90),
                user: User = Depends(admin_guard)):
    return success(data=stats_service.daily_trend(db, days))


@router.get("/hot-questions", response_model=ResponseSchema, summary="热门问题Top")
def hot_questions(top_n: int = Query(10, ge=1, le=50), db: Session = Depends(get_db),
                  user: User = Depends(admin_guard)):
    return success(data=stats_service.hot_questions(db, top_n))
