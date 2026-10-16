"""知识库业务服务：串起 存储 → 解析 → 分块 → 落库 的完整流程。

分层约定：路由层只管 HTTP（收参数/包响应），本模块只管业务。
上层（接口、前端、测试）都直接复用这些函数，不必发 HTTP。
"""
from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.logger import logger
from app.models.kb import Document, DocumentChunk, KnowledgeBase
from app.services.chunker import split_text
from app.services.parser import SUPPORTED_EXTENSIONS, extract_text
from app.services.storage import delete_file, resolve_path, save_upload
from app.services.rag.pipeline import index_document
from app.services.rag.vector_store import delete_by_doc, delete_by_kb
from app.services.rag.bm25 import invalidate


def create_kb(db, name: str, description: str = "") -> KnowledgeBase:
    kb = KnowledgeBase(name=name, description=description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def get_kb(db, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessException(code=404, message="知识库不存在")
    return kb


def process_document(db, kb_id: int, filename: str, content: bytes) -> Document:
    """同步处理一份上传文档：存盘→解析→分块→入库，全程维护 parse_status。"""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise BusinessException(code=400, message=f"不支持的文件类型: {ext}")

    doc = Document(kb_id=kb_id, filename=filename,
                   file_path="", parse_status="processing")
    db.add(doc)
    db.commit()          # ② 先落"受理回执"，失败也有痕
    db.refresh(doc)

    try:
        doc.file_path = save_upload(content, kb_id, filename)
        text = extract_text(str(resolve_path(doc.file_path)))
        chunks = split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        rows = [{"doc_id": doc.id, "kb_id": kb_id,
                 "content": c, "chunk_index": i}
                for i, c in enumerate(chunks)]
        db.bulk_insert_mappings(DocumentChunk, rows)   # 一条 SQL 批量插
        indexed = index_document(db, doc)
        logger.info(f"文档向量化完成 doc={doc.id} 向量数={indexed}")
        doc.parse_status = "success"
        logger.info(f"文档处理成功 doc={doc.id} 分块数={len(chunks)}")
    except Exception as e:
        doc.parse_status = "failed"
        logger.warning(f"文档处理失败 doc={doc.id} file={filename}: {e}")
    db.commit()
    db.refresh(doc)
    invalidate(kb_id)        # 新块入库，作废旧索引，下次检索重建
    return doc


def delete_document(db, doc_id: int) -> None:
    """删除文档：磁盘文件 + ORM 级联删分块。

    注意：必须用 db.delete(对象) 走 ORM，级联(cascade)才生效；
    db.query(Document).filter(...).delete() 是批量 SQL，不触发级联！
    """
    doc = db.get(Document, doc_id)
    if not doc:
        raise BusinessException(code=404, message="文档不存在")
    kb_id = doc.kb_id                    # 删除前先抄下 kb_id（对象删后属性失效）
    if doc.file_path:
        delete_by_doc(doc_id)
        delete_file(doc.file_path)
    db.delete(doc)
    db.commit()
    invalidate(kb_id)                    # 块没了，索引作废


def update_kb_description(db, kb_id: int, description: str) -> KnowledgeBase:
    """仅更新知识库描述；名称锁定，不允许修改。"""
    kb = get_kb(db, kb_id)
    kb.description = description
    db.commit()
    db.refresh(kb)
    return kb


def delete_kb(db, kb_id: int) -> None:
    """删除知识库：级联清理文档/分块/向量/磁盘文件/BM25 缓存。

    必须用 db.delete(对象) 走 ORM，级联(cascade)才生效；
    文档的 file_path 在删除前逐一收集，删完对象后属性失效。
    """
    kb = get_kb(db, kb_id)
    # 收集所有文档的磁盘路径，删对象后属性就没了
    file_paths = [d.file_path for d in kb.documents if d.file_path]
    # 向量按 kb_id 一次性清，比逐文档删更高效
    delete_by_kb(kb_id)
    for fp in file_paths:
        delete_file(fp)
    db.delete(kb)                        # ORM 级联：documents → chunks
    db.commit()
    invalidate(kb_id)                    # BM25 缓存作废
    logger.info(f"知识库已删除 kb={kb_id} 文档数={len(file_paths)}")