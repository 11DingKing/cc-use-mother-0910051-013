from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.models import (
    StaffType, SessionType, SessionStatus,
    AssignmentRole, AudienceType, WarningType,
    ChangeType, ChangeStatus, ConflictType, RescheduleStatus,
    PointSourceType
)


class StaffThemeBase(BaseModel):
    theme_id: int
    proficiency_level: int = 3


class StaffThemeCreate(StaffThemeBase):
    pass


class StaffTheme(StaffThemeBase):
    id: int
    theme_name: str

    class Config:
        from_attributes = True


class StaffVenueBase(BaseModel):
    venue_id: int
    is_certified: bool = True


class StaffVenueCreate(StaffVenueBase):
    pass


class StaffVenue(StaffVenueBase):
    id: int
    venue_name: str

    class Config:
        from_attributes = True


class StaffBase(BaseModel):
    name: str
    staff_type: StaffType
    phone: Optional[str] = None
    email: Optional[str] = None


class StaffCreate(StaffBase):
    themes: List[StaffThemeCreate] = []
    venues: List[StaffVenueCreate] = []


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    themes: Optional[List[StaffThemeCreate]] = None
    venues: Optional[List[StaffVenueCreate]] = None


class Staff(StaffBase):
    id: int
    total_service_hours: float
    star_rating: float
    review_count: int
    is_active: bool
    total_points: int
    current_level: int
    current_badge_id: Optional[int] = None
    is_excellent: bool
    excellent_until: Optional[datetime] = None
    themes: List[StaffTheme] = []
    venues: List[StaffVenue] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ThemeBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


class ThemeCreate(ThemeBase):
    pass


class ThemeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


class Theme(ThemeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class VenueBase(BaseModel):
    name: str
    venue_type: str
    capacity: Optional[int] = None
    location: Optional[str] = None


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    venue_type: Optional[str] = None
    capacity: Optional[int] = None
    location: Optional[str] = None


class Venue(VenueBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SchoolBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None


class School(SchoolBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentBase(BaseModel):
    staff_id: int
    role: AssignmentRole
    is_primary: bool = False


class AssignmentCreate(AssignmentBase):
    pass


class Assignment(AssignmentBase):
    id: int
    staff_name: str
    staff_type: str
    star_rating: float
    created_at: datetime

    class Config:
        from_attributes = True


class SessionBase(BaseModel):
    title: str
    theme_id: int
    venue_id: int
    session_type: SessionType
    start_time: datetime
    end_time: datetime
    audience_type: AudienceType
    audience_count: int = 0
    school_id: Optional[int] = None
    guides_needed: int = 0
    needs_lecturer: bool = False
    description: Optional[str] = None


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    theme_id: Optional[int] = None
    venue_id: Optional[int] = None
    session_type: Optional[SessionType] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    audience_type: Optional[AudienceType] = None
    audience_count: Optional[int] = None
    school_id: Optional[int] = None
    guides_needed: Optional[int] = None
    needs_lecturer: Optional[bool] = None
    description: Optional[str] = None
    status: Optional[SessionStatus] = None


class Session(SessionBase):
    id: int
    status: SessionStatus
    theme_name: str
    venue_name: str
    school_name: Optional[str] = None
    assignments: List[Assignment] = []
    is_fully_staffed: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionWithDetails(Session):
    pass


class ReviewBase(BaseModel):
    session_id: int
    reviewer_name: Optional[str] = None
    reviewer_type: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewCreate(ReviewBase):
    pass


class Review(ReviewBase):
    id: int
    session_title: str
    created_at: datetime

    class Config:
        from_attributes = True


class WarningBase(BaseModel):
    theme_id: Optional[int] = None
    warning_type: WarningType
    message: str


class WarningCreate(WarningBase):
    pass


class Warning(WarningBase):
    id: int
    resolved: bool
    theme_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentValidationResult(BaseModel):
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ThemeSessionStats(BaseModel):
    theme_id: int
    theme_name: str
    session_count: int
    guide_count: int


class StaffSaturationStats(BaseModel):
    staff_id: int
    staff_name: str
    staff_type: str
    assigned_hours: float
    available_hours: float
    saturation_rate: float


class StaffRankingItem(BaseModel):
    staff_id: int
    staff_name: str
    staff_type: str
    total_service_hours: float
    star_rating: float
    review_count: int
    session_count: int


class StaffRecommendation(BaseModel):
    staff_id: int
    staff_name: str
    star_rating: float
    proficiency_level: int
    is_certified: bool
    is_available: bool
    score: float


class BulkAssignmentResponse(BaseModel):
    success: bool
    message: str
    assigned_staff: List[int] = []
    errors: List[str] = []


class ChangeRequestBase(BaseModel):
    session_id: int
    requester: str
    change_type: ChangeType
    new_start_time: Optional[datetime] = None
    new_end_time: Optional[datetime] = None
    new_audience_count: Optional[int] = None
    new_guides_needed: Optional[int] = None
    reason: Optional[str] = None


class ChangeRequestCreate(ChangeRequestBase):
    pass


class ChangeRequestReview(BaseModel):
    status: ChangeStatus
    reviewer: str
    review_comment: Optional[str] = None


class ChangeRequest(ChangeRequestBase):
    id: int
    old_start_time: Optional[datetime] = None
    old_end_time: Optional[datetime] = None
    old_audience_count: Optional[int] = None
    old_guides_needed: Optional[int] = None
    status: ChangeStatus
    reviewer: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    session_title: Optional[str] = None
    conflict_count: int = 0
    suggestion_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChangeRequestWithDetails(ChangeRequest):
    conflicts: List["SessionConflict"] = []
    suggestions: List["RescheduleSuggestion"] = []


class SessionConflictBase(BaseModel):
    conflict_type: ConflictType
    message: str
    detail: Optional[str] = None


class SessionConflictCreate(SessionConflictBase):
    change_request_id: int
    staff_id: Optional[int] = None
    assignment_id: Optional[int] = None


class SessionConflict(SessionConflictBase):
    id: int
    change_request_id: int
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None
    assignment_id: Optional[int] = None
    status: RescheduleStatus
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RescheduleSuggestionBase(BaseModel):
    action: str
    priority: int = 5
    reason: Optional[str] = None


class RescheduleSuggestionCreate(RescheduleSuggestionBase):
    change_request_id: int
    conflict_id: Optional[int] = None
    staff_id: Optional[int] = None
    suggested_staff_id: Optional[int] = None


class RescheduleSuggestion(RescheduleSuggestionBase):
    id: int
    change_request_id: int
    conflict_id: Optional[int] = None
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None
    suggested_staff_id: Optional[int] = None
    suggested_staff_name: Optional[str] = None
    is_applied: bool
    applied_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChangeHistoryBase(BaseModel):
    session_id: int
    operator: str
    action: str
    description: Optional[str] = None


class ChangeHistoryCreate(ChangeHistoryBase):
    change_request_id: Optional[int] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    change_type: Optional[ChangeType] = None


class ChangeHistory(ChangeHistoryBase):
    id: int
    change_request_id: Optional[int] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    change_type: Optional[ChangeType] = None
    session_title: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConflictCheckResult(BaseModel):
    has_conflicts: bool
    conflicts: List[SessionConflict] = []
    suggestions: List[RescheduleSuggestion] = []
    summary: str


class ChangeExecuteResult(BaseModel):
    success: bool
    message: str
    applied_suggestions: int = 0
    remaining_conflicts: int = 0
    errors: List[str] = []


class SessionChangeStats(BaseModel):
    session_id: int
    session_title: str
    change_count: int
    time_change_count: int
    count_change_count: int
    last_changed_at: Optional[datetime] = None


class ChangeFrequencyStats(BaseModel):
    period: str
    total_changes: int
    time_changes: int
    count_changes: int
    both_changes: int
    approved_count: int
    rejected_count: int
    avg_resolution_time_hours: float


ChangeRequestWithDetails.model_rebuild()


class LevelBadgeBase(BaseModel):
    level: int
    name: str
    badge_name: str
    min_points: int
    max_points: Optional[int] = None
    description: Optional[str] = None
    icon: Optional[str] = None


class LevelBadgeCreate(LevelBadgeBase):
    pass


class LevelBadgeUpdate(BaseModel):
    name: Optional[str] = None
    badge_name: Optional[str] = None
    min_points: Optional[int] = None
    max_points: Optional[int] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class LevelBadge(LevelBadgeBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PointRecordBase(BaseModel):
    staff_id: int
    source_type: PointSourceType
    points: int
    description: Optional[str] = None


class PointRecordCreate(PointRecordBase):
    session_id: Optional[int] = None
    review_id: Optional[int] = None


class PointRecord(PointRecordBase):
    id: int
    session_id: Optional[int] = None
    review_id: Optional[int] = None
    level_badge_id: Optional[int] = None
    balance_after: int
    session_title: Optional[str] = None
    level_badge_name: Optional[str] = None
    # 业务归属月（按服务事实场次时间），为空表示按处理时间归属的普通即时积分
    service_year: Optional[int] = None
    service_month: Optional[int] = None
    fact_key: Optional[str] = None
    replaces_id: Optional[int] = None
    is_voided: bool = False
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    operator: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StaffBadgeBase(BaseModel):
    staff_id: int
    level_badge_id: int


class StaffBadge(StaffBadgeBase):
    id: int
    earned_at: datetime
    is_current: bool
    level_badge_name: str
    level: int
    icon: Optional[str] = None

    class Config:
        from_attributes = True


class MonthlyRankingBase(BaseModel):
    staff_id: int
    year: int
    month: int
    rank: int
    total_points: int
    positive_review_rate: float
    session_count: int
    is_excellent: bool = False


class MonthlyRanking(MonthlyRankingBase):
    id: int
    staff_name: str
    level_badge_id: Optional[int] = None
    level_badge_name: Optional[str] = None
    top_n: int = 3
    status: str = "已结算"
    revision: int = 1
    settled_at: datetime
    adjusted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StaffWithDetails(Staff):
    total_points: int
    current_level: int
    current_badge_name: Optional[str] = None
    current_badge_icon: Optional[str] = None
    is_excellent: bool
    excellent_until: Optional[datetime] = None
    badges: List[StaffBadge] = []


class PointChangeResult(BaseModel):
    success: bool
    staff_id: int
    points_added: int
    new_balance: int
    level_up: bool = False
    new_level: Optional[int] = None
    new_badge: Optional[LevelBadge] = None
    message: str


class MonthlySettleResult(BaseModel):
    success: bool
    year: int
    month: int
    total_staff: int
    excellent_staff: List[int] = []
    message: str
    action: str = "settled"  # settled / recalculated
    revision: int = 1
    changed_staff: List[int] = []


class ServicePointBackfillRequest(BaseModel):
    """为已完成场次补录/更正某讲解员的服务积分"""
    staff_id: int
    points: int = Field(ge=0, description="更正后的该场服务积分（0 表示撤销该场服务积分）")
    operator: Optional[str] = None
    reason: Optional[str] = None


class ServicePointResult(BaseModel):
    success: bool
    message: str
    staff_id: int
    session_id: int
    points: int
    # idempotent / corrected / created
    action: str
    point_record_id: Optional[int] = None
    service_year: Optional[int] = None
    service_month: Optional[int] = None
    # 该笔积分影响到的月度结果（未结算则为空）
    monthly_affected: Optional["MonthlyAffectedInfo"] = None
    balance_after: int = 0


class MonthlyAffectedInfo(BaseModel):
    year: int
    month: int
    ranking_status: str
    old_total_points: Optional[int] = None
    new_total_points: Optional[int] = None
    old_rank: Optional[int] = None
    new_rank: Optional[int] = None
    revision: Optional[int] = None
    adjustment_id: Optional[int] = None


class PointAttribution(BaseModel):
    """一笔积分的完整归属解释"""
    point_record_id: int
    staff_id: int
    staff_name: str
    points: int
    source_type: PointSourceType
    description: Optional[str] = None
    # 服务事实
    session_id: Optional[int] = None
    session_title: Optional[str] = None
    session_start_time: Optional[datetime] = None
    session_end_time: Optional[datetime] = None
    review_id: Optional[int] = None
    # 归属月与处理时间
    service_year: Optional[int] = None
    service_month: Optional[int] = None
    attribution_basis: str  # 服务事实 / 处理时间
    created_at: datetime
    operator: Optional[str] = None
    is_voided: bool = False
    replaces_id: Optional[int] = None
    void_reason: Optional[str] = None
    # 影响了哪次月度结果
    monthly_impacts: List["MonthlyImpactItem"] = []


class MonthlyImpactItem(BaseModel):
    year: int
    month: int
    ranking_status: str
    rank: Optional[int] = None
    total_points: Optional[int] = None
    revision: int = 1
    adjusted_at: Optional[datetime] = None


class MonthlyRankingAdjustmentOut(BaseModel):
    id: int
    ranking_id: Optional[int]
    year: int
    month: int
    staff_id: int
    staff_name: str
    point_record_id: Optional[int] = None
    reason: str
    old_total_points: Optional[int] = None
    new_total_points: Optional[int] = None
    old_rank: Optional[int] = None
    new_rank: Optional[int] = None
    operator: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PointTrendItem(BaseModel):
    date: str
    points: int
    staff_count: int


class LevelDistributionItem(BaseModel):
    level: int
    level_name: str
    badge_name: str
    staff_count: int
    percentage: float


class StaffPointDetail(StaffRankingItem):
    total_points: int
    current_level: int
    current_badge_name: Optional[str] = None
    is_excellent: bool
    positive_review_rate: float
    monthly_points: int = 0


# 解析上述模型中的前向引用（ServicePointResult -> MonthlyAffectedInfo 等）
ServicePointResult.model_rebuild()
PointAttribution.model_rebuild()
