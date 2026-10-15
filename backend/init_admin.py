from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
import os

DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")   # 不给默认值，强制外部传入

if not DEFAULT_ADMIN_PASSWORD:
    raise SystemExit("请先设置环境变量 ADMIN_PASSWORD")

def init_admin():
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if exists:
            print("管理员账号已存在，跳过")
            return
        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=User.ROLE_ADMIN,
            status=1,
        )
        db.add(admin)
        db.commit()
        print("默认管理员创建成功")
        print("账号：", DEFAULT_ADMIN_USERNAME)
        print("密码：", DEFAULT_ADMIN_PASSWORD, "（请尽快修改）")
    finally:
        db.close()


if __name__ == "__main__":
    init_admin()
