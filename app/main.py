from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import engine, Base
from app.routers import staff, themes, venues, schools, sessions, reviews, warnings, statistics, changes, ranking, points


def _run_sqlite_migrations():
    """为已存在的库补齐积分归属相关列/表（幂等）。

    * 历史服务积分（有场次）按场次结束时间回填业务归属月，使其从此按业务事实统计；
      已结算榜单不自动变动，只有显式重算/补录更正才产生调整。
    * 历史普通即时积分（无场次）保持 NULL，继续按处理时间归属。
    * 已经发放的余额、等级、勋章均不变，既有成长记录不回归。
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        return
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "point_records" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("point_records")}
            point_columns = {
                "service_year": "INTEGER",
                "service_month": "INTEGER",
                "fact_key": "VARCHAR(120)",
                "replaces_id": "INTEGER",
                "is_voided": "BOOLEAN DEFAULT 0 NOT NULL",
                "voided_at": "DATETIME",
                "void_reason": "TEXT",
                "operator": "VARCHAR(100)",
            }
            for name, ddl in point_columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE point_records ADD COLUMN {name} {ddl}"))
            indexes = {ix["name"] for ix in inspector.get_indexes("point_records")}
            if "ix_point_records_service_month" not in indexes:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_point_records_service_month "
                    "ON point_records (service_year, service_month)"
                ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_point_records_fact_key "
                "ON point_records (fact_key)"
            ))
            # 回填历史服务积分的业务月（仅回填尚未归属、且能找到场次的记录）
            conn.execute(text(
                """
                UPDATE point_records
                   SET service_year = CAST(strftime('%Y', sessions.end_time) AS INTEGER),
                       service_month = CAST(strftime('%m', sessions.end_time) AS INTEGER)
                  FROM sessions
                 WHERE point_records.session_id = sessions.id
                   AND point_records.service_year IS NULL
                   AND point_records.source_type = 'SERVICE'
                """
            ))
            # 为历史上"每讲解员每场仅一笔"的事实补幂等键；一场多笔的历史数据
            # （旧版本多评价重复发分）不自动作废、不改余额，保留 fact_key=NULL，
            # 由后续人工"更正"一次性归并，保证已结算数据与总积分不被迁移悄悄改动。
            conn.execute(text(
                """
                UPDATE point_records
                   SET fact_key = 'service:' || staff_id || ':' || session_id
                 WHERE source_type = 'SERVICE' AND session_id IS NOT NULL
                   AND fact_key IS NULL AND is_voided = 0
                   AND id IN (
                       SELECT MAX(id) FROM point_records
                        WHERE source_type = 'SERVICE' AND session_id IS NOT NULL
                          AND is_voided = 0
                        GROUP BY staff_id, session_id
                        HAVING COUNT(*) = 1
                   )
                """
            ))

        if "monthly_rankings" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("monthly_rankings")}
            ranking_columns = {
                "top_n": "INTEGER DEFAULT 3 NOT NULL",
                "status": "VARCHAR(20) DEFAULT '已结算' NOT NULL",
                "revision": "INTEGER DEFAULT 1 NOT NULL",
                "adjusted_at": "DATETIME",
            }
            for name, ddl in ranking_columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE monthly_rankings ADD COLUMN {name} {ddl}"))


Base.metadata.create_all(bind=engine)
_run_sqlite_migrations()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="遗产日活动排班管理系统 - 讲解员和讲师排班、场次管理、评价统计、变更联动重排"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(staff.router)
app.include_router(themes.router)
app.include_router(venues.router)
app.include_router(schools.router)
app.include_router(sessions.router)
app.include_router(reviews.router)
app.include_router(warnings.router)
app.include_router(statistics.router)
app.include_router(changes.router)
app.include_router(ranking.router)
app.include_router(points.router)


@app.get("/", tags=["系统"])
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health", tags=["系统"])
def health_check():
    return {"status": "healthy"}
