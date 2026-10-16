from fastapi import APIRouter

from app.schemas.common import ResponseSchema, success

router = APIRouter()


@router.get("/health", response_model=ResponseSchema, summary="健康检查")
def health_check():
    return success(data={"status": "ok"})