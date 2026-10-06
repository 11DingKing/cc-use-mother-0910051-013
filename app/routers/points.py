from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, crud

router = APIRouter(tags=["服务积分"])


@router.post(
    "/api/sessions/{session_id}/service-points",
    response_model=schemas.ServicePointResult
)
def backfill_session_service_points(
    session_id: int,
    body: schemas.ServicePointBackfillRequest,
    db: Session = Depends(get_db)
):
    """为已完成场次补录/更正某讲解员的服务积分。

    积分严格按场次结束时间所在自然月归属（业务月），处理时间仅作审计；
    同一讲解员同一场次重复提交相同分值幂等返回，不重复计入；
    若归属月榜单已结算，会同步产生一笔可查询的榜单调整。
    """
    result = crud.backfill_service_points(
        db,
        staff_id=body.staff_id,
        session_id=session_id,
        points=body.points,
        operator=body.operator,
        reason=body.reason
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get(
    "/api/points/{point_record_id}/attribution",
    response_model=schemas.PointAttribution
)
def get_point_attribution(point_record_id: int, db: Session = Depends(get_db)):
    """解释一笔积分：对应哪个服务事实（场次/评价）、归属哪个自然月、
    影响了哪次月度结果（未结算/已结算/已调整及版本、名次）"""
    attribution = crud.get_point_attribution(db, point_record_id)
    if not attribution:
        raise HTTPException(status_code=404, detail="积分记录不存在")
    return attribution
