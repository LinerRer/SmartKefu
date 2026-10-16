"""上传文件的落盘与删除。

安全原则：永远不信任客户端传来的 filename——
它可能含路径穿越（../../etc/x）或故意撞名覆盖。
所以磁盘上用 uuid 重命名，原始文件名只存数据库用于展示。
"""
import uuid
from pathlib import Path
from app.core.config import BACKEND_ROOT


UPLOAD_ROOT = BACKEND_ROOT / "data" / "uploads"


def save_upload(content: bytes, kb_id: int, filename: str) -> str:
    """写入 uploads/kb/{kb_id}/{uuid}.{ext}，返回相对 backend 根的路径（入库用）。"""
    ext = Path(filename).suffix.lower()
    dest_dir = UPLOAD_ROOT / "kb" / str(kb_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(content)
    return str(dest.relative_to(BACKEND_ROOT))


def resolve_path(rel: str) -> Path:
    """把数据库里的相对路径解析成真实路径——所有碰磁盘的地方都过这一手。"""
    return BACKEND_ROOT / rel


def delete_file(file_path: str) -> None:
    resolve_path(file_path).unlink(missing_ok=True)