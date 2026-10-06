from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/api/ranking", tags=["月度榜单"])


@router.post("/settle", response_model=schemas.MonthlySettleResult)
def settle_monthly_ranking(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    top_n: int = Query(3, ge=1, le=10, description="优秀讲解员数量"),
    recalculate: bool = Query(False, description="已结算月份是否重算（撤销旧结果后按当前积分重新结算）"),
    db: Session = Depends(get_db)
):
    """结算月度榜单，自动标记优秀讲解员

    榜单按积分的业务事实时间归属统计。已结算的月份默认拒绝重复结算；
    补录或更正历史积分后，使用 recalculate=true 显式重算该月榜单。
    """
    result = crud.settle_monthly_ranking(db, year, month, top_n, recalculate=recalculate)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get("", response_model=List[schemas.MonthlyRanking])
def get_monthly_ranking(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db)
):
    """获取月度榜单"""
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
            version=r.version or 1,
            settled_at=r.settled_at
        ))
    return result


@router.get("/point-records/{record_id}", response_model=schemas.PointAttribution)
def get_point_record_attribution(record_id: int, db: Session = Depends(get_db)):
    """解释一笔积分的归属：属于哪个服务事实、影响了哪次月度结果

    返回业务事实（场次/评价）、业务发生时间、处理时间、归属月份，
    以及该归属月份的榜单结算状态与上榜结果。
    """
    attribution = crud.get_point_attribution(db, record_id)
    if not attribution:
        raise HTTPException(status_code=404, detail="积分记录不存在")
    return attribution


@router.get("/current", response_model=List[schemas.StaffPointDetail])
def get_current_ranking(
    year: Optional[int] = Query(None, description="年份，默认当前年"),
    month: Optional[int] = Query(None, description="月份，默认当前月"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取当前月度实时排行（未结算）"""
    return crud.get_staff_point_details(db, year, month, limit)
