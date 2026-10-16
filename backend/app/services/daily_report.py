"""日报生成：汇总指定日期的核心指标，写入 data/reports/ 下的 markdown。

由 APScheduler 每天 01:00 调用（main.py lifespan 注册）。
手动生成：python -m app.services.daily_report [YYYY-MM-DD]
"""
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logger import logger
from app.services import stats_service

REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


def generate_report(db: Session, target: date | None = None) -> Path:
    """生成 target 日期（默认昨天）的日报文件，返回路径。"""
    target = target or (datetime.now() - timedelta(days=1)).date()
    trend = stats_service.daily_trend(db, days=2)
    day_row = next((t for t in trend if t["date"] == str(target)), None)
    ov = stats_service.overview(db)          # 全局口径（v1 简化：满意度/首响为累计值）
    hot = stats_service.hot_questions(db, 5)

    lines = [
        f"# SmartKefu 日报 {target}",
        "",
        f"- 当日会话量：{day_row['conversations'] if day_row else 0}",
        f"- 当日转人工数：{day_row['to_human'] if day_row else 0}",
        f"- 累计转人工率：{ov['to_human_rate'] * 100:.1f}%",
        f"- 累计 AI 独立解决率：{ov['ai_solved_rate'] * 100:.1f}%",
        f"- 平均满意度：{ov['avg_rating'] if ov['avg_rating'] is not None else '暂无数据'}",
        f"- 平均首响时长：{stats_service.first_response_seconds(db)} 秒",
        "",
        "## 热门问题 Top5",
        *[f"{i + 1}. {h['question']}（{h['count']} 次）" for i, h in enumerate(hot)],
        "",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"report_{target}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"日报已生成：{path}")
    return path


def run_daily_job() -> None:
    """调度器入口：自建 Session，用完即关（不依赖请求上下文）。"""
    db = SessionLocal()
    try:
        generate_report(db)
    except Exception:
        logger.exception("日报生成失败")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    d = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else None
    _db = SessionLocal()
    try:
        print(generate_report(_db, d))
    finally:
        _db.close()
