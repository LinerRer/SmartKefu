from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from app.core.logger import logger
from app.schemas.common import ResponseSchema


# 自定义业务异常（业务主动抛出，比如知识库不存在、权限不足）
class BusinessException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


# 捕获我们自定义的业务异常
async def business_exception_handler(request: Request, exc: BusinessException):
    logger.warning(f"业务异常: code={exc.code}, message={exc.message}")
    return JSONResponse(
        content=ResponseSchema(code=exc.code,message=exc.message,data=None).model_dump()
    )


# 捕获FastAPI自带HTTP异常（404、401这类http标准错误）
async def http_exception_handle(request: Request, exc: HTTPException):
    logger.warning(f"HTTP异常：status={exc.status_code}, msg={exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,   # 必须透传真实HTTP码：前端Axios拦截器靠它判断401跳登录
        content=ResponseSchema(code=exc.status_code,message=exc.detail).model_dump()
    )


from fastapi.exceptions import RequestValidationError

# 捕获参数校验异常（422：字段缺失/类型不对/min_length不满足等）
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]  # 只取第一条，报错信息给用户看要短
    field = ".".join(str(loc) for loc in first["loc"][1:])  # loc[0]是"body"，从[1:]起才是字段
    logger.warning(f"参数校验失败: {field} -> {first['msg']}")
    return JSONResponse(
        status_code=422,
        content=ResponseSchema(code=422, message=f"参数校验失败: {field}, {first['msg']}").model_dump()
    )


# 兜底捕获所有未知系统异常（数据库报错、代码bug等500错误）
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("服务器未知异常")
    return JSONResponse(
        content=ResponseSchema(code=500, message="服务器内部错误", data=None).model_dump()
    )


# 注册异常处理器到app实例
def register_exception(app: FastAPI):
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handle)
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)