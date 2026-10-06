from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """轻量级迁移：为积分归属修复补充新列并回填历史数据。

    - point_records 增加 occurred_at（业务事实时间）、idempotency_key、
      corrects_record_id、is_superseded 列；
    - 历史记录的 occurred_at 优先回填为关联场次的结束时间（业务事实），
      无关联场次时回填为处理时间 created_at，保证既有成长记录归属不变；
    - monthly_rankings 增加 version 列用于结算重算。
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    with engine.begin() as conn:
        if "point_records" in table_names:
            columns = {c["name"] for c in inspector.get_columns("point_records")}
            if "occurred_at" not in columns:
                conn.execute(text("ALTER TABLE point_records ADD COLUMN occurred_at DATETIME"))
            if "idempotency_key" not in columns:
                conn.execute(text("ALTER TABLE point_records ADD COLUMN idempotency_key VARCHAR(100)"))
            if "corrects_record_id" not in columns:
                conn.execute(text("ALTER TABLE point_records ADD COLUMN corrects_record_id INTEGER"))
            if "is_superseded" not in columns:
                conn.execute(text("ALTER TABLE point_records ADD COLUMN is_superseded BOOLEAN DEFAULT 0"))

        if "monthly_rankings" in table_names:
            columns = {c["name"] for c in inspector.get_columns("monthly_rankings")}
            if "version" not in columns:
                conn.execute(text("ALTER TABLE monthly_rankings ADD COLUMN version INTEGER DEFAULT 1"))

    if "point_records" not in table_names:
        return

    # 用 ORM 回填，避免直接拼接枚举值
    from app.models import PointRecord, Session as SessionModel, PointSourceType

    db = SessionLocal()
    try:
        missing_occurred = db.query(PointRecord).filter(PointRecord.occurred_at.is_(None)).all()
        for record in missing_occurred:
            session = None
            if record.session_id:
                session = db.query(SessionModel).filter(SessionModel.id == record.session_id).first()
            record.occurred_at = (session.end_time if session and session.end_time else None) or record.created_at

        missing_key = db.query(PointRecord).filter(
            PointRecord.idempotency_key.is_(None),
            PointRecord.source_type == PointSourceType.SERVICE,
        ).all()
        for record in missing_key:
            if record.review_id:
                record.idempotency_key = f"review:{record.review_id}:{record.staff_id}"
            elif record.session_id:
                record.idempotency_key = f"service:{record.staff_id}:{record.session_id}"

        db.commit()
    finally:
        db.close()
