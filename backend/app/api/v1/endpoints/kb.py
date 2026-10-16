"""知识库路由：只做 HTTP 的事——收参数、调服务、包响应。

权限约定（v1.1 安全加固）：
- 读类接口需登录（admin 或 agent）；
- 写/删类接口仅 admin；
- /public 是唯一匿名接口，供访客端选知识库下拉，只返回 id+name（最小暴露面）。
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import require_role
from app.core.database import get_db
from app.models.kb import Document, DocumentChunk, KnowledgeBase
from app.models.user import User
from app.schemas.common import ResponseSchema, success
from app.services.kb_service import (
    create_kb,
    delete_document,
    delete_kb,
    get_kb,
    process_document,
    update_kb_description,
)
from app.services.rag import hybrid
from app.schemas.kb import KBCreate, KBUpdate, SearchTestBody

router = APIRouter()

admin_guard = require_role(User.ROLE_ADMIN)                    # 仅管理员
staff_guard = require_role(User.ROLE_ADMIN, User.ROLE_AGENT)   # 管理员 + 坐席


@router.get("/public", response_model=ResponseSchema,
            summary="公开知识库列表（访客端用，仅返回 id+name）")
def list_public_kbs(db: Session = Depends(get_db)):
    """匿名可访问：访客聊天页选库下拉用，故意只暴露最小字段。"""
    rows = db.query(KnowledgeBase).order_by(KnowledgeBase.id).all()
    return success(data=[{"id": r.id, "name": r.name} for r in rows])


@router.post("",response_model=ResponseSchema,summary="创建知识库")
def add_kb(body: KBCreate, db: Session = Depends(get_db),
           user: User = Depends(admin_guard)):
    kb = create_kb(db,body.name, body.description)
    return success(data={"id": kb.id, "name": kb.name})


@router.put("/{kb_id}", response_model=ResponseSchema, summary="更新知识库描述（名称锁定不可改）")
def update_kb(kb_id: int, body: KBUpdate, db: Session = Depends(get_db),
              user: User = Depends(admin_guard)):
    kb = update_kb_description(db, kb_id, body.description)
    return success(data={"id": kb.id, "name": kb.name, "description": kb.description})


@router.delete("/{kb_id}", response_model=ResponseSchema, summary="删除知识库（级联清理文档/分块/向量）")
def remove_kb(kb_id: int, db: Session = Depends(get_db),
              user: User = Depends(admin_guard)):
    delete_kb(db, kb_id)
    return success(message="知识库已删除")


@router.get("", response_model=ResponseSchema, summary="知识库列表")
def list_kbs(db: Session = Depends(get_db),
             user: User = Depends(staff_guard)):
    rows = db.query(KnowledgeBase).order_by(KnowledgeBase.id).all()
    data = []
    for r in rows:
        doc_count = db.query(func.count(Document.id)).filter_by(kb_id=r.id).scalar()
        data.append({
            "id": r.id,
            "name": r.name,
            "description": r.description or "",
            "doc_count": doc_count,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None,
        })
    return success(data=data)


@router.post("/documents", response_model=ResponseSchema, summary="上传并处理文档")
async def upload_document(
    kb_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(admin_guard),
):
    get_kb(db, kb_id)               # 知识库不存在直接 404，不浪费解析
    content = await file.read()
    doc = process_document(db, kb_id, file.filename, content)
    return success(data={"document_id": doc.id, "parse_status": doc.parse_status})


@router.get("/documents", response_model=ResponseSchema, summary="文档列表")
def list_documents(kb_id: int = Query(...), db: Session = Depends(get_db),
                   user: User = Depends(staff_guard)):
    rows = db.query(Document).filter_by(kb_id=kb_id).order_by(Document.id).all()
    data = []
    for r in rows:
        chunk_count = db.query(func.count(DocumentChunk.id)).filter_by(doc_id=r.id).scalar()
        char_count = db.query(
            func.coalesce(func.sum(func.char_length(DocumentChunk.content)), 0)
        ).filter_by(doc_id=r.id).scalar()
        ext = r.filename.rsplit(".", 1)[-1].lower() if "." in r.filename else ""
        data.append({
            "id": r.id,
            "filename": r.filename,
            "file_type": ext,
            "parse_status": r.parse_status,
            "chunk_count": chunk_count,
            "char_count": int(char_count or 0),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None,
        })
    return success(data=data)


@router.get("/documents/{doc_id}/chunks", response_model=ResponseSchema,
            summary="分页查看分块")
def list_chunks(
        doc_id: int,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        db: Session = Depends(get_db),
        user: User = Depends(staff_guard),
):
        total = db.query(func.count(DocumentChunk.id)).filter_by(doc_id=doc_id).scalar()
        rows = (
            db.query(DocumentChunk)
            .filter_by(doc_id=doc_id)
            .order_by(DocumentChunk.chunk_index)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return success(data={
            "total": total,
            "page": page,
            "items": [{"chunk_index": r.chunk_index, "content": r.content} for r in rows],
        })


@router.delete("/documents/{doc_id}", response_model=ResponseSchema,
               summary="删除文档（级联+清盘）")
def remove_document(doc_id: int, db: Session = Depends(get_db),
                    user: User = Depends(admin_guard)):
    delete_document(db, doc_id)
    return success(message="删除成功")


@router.post("/search-test", response_model=ResponseSchema, summary="检索测试")
def search_test(body: SearchTestBody, db: Session = Depends(get_db),
                user: User = Depends(staff_guard)):
    get_kb(db, body.kb_id)
    result = hybrid.search(db, body.query, body.kb_id, body.top_k)
    return success(data=result)
