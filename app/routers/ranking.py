from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import schemas, crud
from app.models import MonthlyRanking

router = APIRouter(prefix="/api/ranking", tags=["月度榜单"])


@router.post("/settle", response_model=schemas.MonthlySettleResult)
def settle_monthly_ranking(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    top_n: int = Query(3, ge=1, le=10, description="优秀讲解员数量"),
    operator: Optional[str] = Query(None, description="操作人（审计）"),
    force_recalculate: bool = Query(False, description="已结算时是否按最新台账重算"),
    db: Session = Depends(get_db)
):
    """结算月度榜单，自动标记优秀讲解员。

    - 首次：按业务归属月台账结算；
    - 已结算且未指定重算：拒绝并提示，保证重复请求不会重复计入；
    - force_recalculate=true：按最新台账显式重算，台账未变则结果不变。
    """
    from app.models import MonthlyRanking
    exists = db.query(MonthlyRanking).filter(
        MonthlyRanking.year == year,
        MonthlyRanking.month == month
    ).first()
    if exists and not force_recalculate:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"{year}年{month}月榜单已结算（版本{exists.revision}）；"
                           f"如需纳入补录/更正请使用 force_recalculate=true 重算",
                "revision": exists.revision,
                "status": exists.status
            }
        )
    result = crud.settle_monthly_ranking(db, year, month, top_n, operator=operator)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get("", response_model=List[schemas.MonthlyRanking])
def get_monthly_ranking(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db)
):
    """获取月度榜单（含结算/调整状态与版本）"""
    rankings = crud.get_monthly_ranking(db, year, month)
    result = []
    for r in rankings:
        result.append(schemas.MonthlyRanking(
            id=r.id,
            staff_id=r.staff_id,
            staff_name=r.staff.name if r.staff else "",
            year=r.year,
            month=r.month,
            rank=r.rank,
            total_points=r.total_points,
            positive_review_rate=r.positive_review_rate,
            session_count=r.session_count,
            is_excellent=r.is_excellent,
            level_badge_id=r.level_badge_id,
            level_badge_name=r.level_badge.badge_name if r.level_badge else None,
            top_n=r.top_n,
            status=r.status,
            revision=r.revision,
            settled_at=r.settled_at,
            adjusted_at=r.adjusted_at
        ))
    return result


@router.get("/current", response_model=List[schemas.StaffPointDetail])
def get_current_ranking(
    year: Optional[int] = Query(None, description="年份，默认当前年"),
    month: Optional[int] = Query(None, description="月份，默认当前月"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取指定月实时排行（未结算）——按业务事实归属月统计，与补录处理时间无关"""
    return crud.get_staff_point_details(db, year, month, limit)


@router.get("/adjustments", response_model=List[schemas.MonthlyRankingAdjustmentOut])
def get_monthly_adjustments(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db)
):
    """查看已结算月份的全部调整审计记录"""
    rows = crud.list_monthly_adjustments(db, year, month)
    return [
        schemas.MonthlyRankingAdjustmentOut(
            id=a.id,
            ranking_id=a.ranking_id,
            year=a.year,
            month=a.month,
            staff_id=a.staff_id,
            staff_name=a.staff.name if a.staff else "",
            point_record_id=a.point_record_id,
            reason=a.reason,
            old_total_points=a.old_total_points,
            new_total_points=a.new_total_points,
            old_rank=a.old_rank,
            new_rank=a.new_rank,
            operator=a.operator,
            created_at=a.created_at
        )
        for a in rows
    ]
