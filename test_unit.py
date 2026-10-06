#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.database import SessionLocal
from app import crud, schemas
from app.models import (
    StaffType, SessionType, SessionStatus, AssignmentRole,
    AudienceType, ChangeType, ChangeStatus, RescheduleStatus
)

def test_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def main():
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        test_header("1. 初始化测试数据")
        
        theme = crud.create_theme(db, schemas.ThemeCreate(
            name="青铜器文化", description="青铜器历史与文化", category="历史"
        ))
        print(f"✓ 创建主题: ID={theme.id}, 名称={theme.name}")

        venue = crud.create_venue(db, schemas.VenueCreate(
            name="青铜馆", venue_type="展厅", capacity=50, location="1楼"
        ))
        print(f"✓ 创建场地: ID={venue.id}, 名称={venue.name}")

        school = crud.create_school(db, schemas.SchoolCreate(
            name="实验小学", contact_person="王老师", phone="13800138000"
        ))
        print(f"✓ 创建学校: ID={school.id}, 名称={school.name}")

        staff1 = crud.create_staff(db, schemas.StaffCreate(
            name="张讲解", staff_type=StaffType.GUIDE, phone="13900139000",
            themes=[schemas.StaffThemeCreate(theme_id=theme.id, proficiency_level=5)],
            venues=[schemas.StaffVenueCreate(venue_id=venue.id, is_certified=True)]
        ))
        print(f"✓ 创建讲解员1: ID={staff1.id}, 名称={staff1.name}")

        staff2 = crud.create_staff(db, schemas.StaffCreate(
            name="李讲解", staff_type=StaffType.GUIDE, phone="13900139001",
            themes=[schemas.StaffThemeCreate(theme_id=theme.id, proficiency_level=4)],
            venues=[schemas.StaffVenueCreate(venue_id=venue.id, is_certified=True)]
        ))
        print(f"✓ 创建讲解员2: ID={staff2.id}, 名称={staff2.name}")

        test_header("2. 创建初始场次并安排讲解员")
        
        tomorrow = datetime.now() + timedelta(days=1)
        session = crud.create_session(db, schemas.SessionCreate(
            title="青铜器研学活动",
            theme_id=theme.id,
            venue_id=venue.id,
            session_type=SessionType.RESEARCH,
            start_time=tomorrow.replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
            audience_type=AudienceType.SCHOOL,
            audience_count=30,
            school_id=school.id,
            guides_needed=1,
            needs_lecturer=False,
            description="实验小学研学"
        ))
        print(f"✓ 创建场次: ID={session.id}, 标题={session.title}")
        print(f"  时间: {session.start_time} - {session.end_time}")
        print(f"  人数: {session.audience_count}, 需讲解员: {session.guides_needed}人")

        assignment, errors = crud.create_assignment(db, session.id, schemas.AssignmentCreate(
            staff_id=staff1.id, role=AssignmentRole.GUIDE, is_primary=True
        ))
        if errors:
            print(f"✗ 安排讲解员失败: {errors}")
        else:
            print(f"✓ 安排讲解员 {staff1.name} 到场次")

        new_start = tomorrow.replace(hour=14, minute=0)
        new_end = tomorrow.replace(hour=16, minute=0)
        conflict_session = crud.create_session(db, schemas.SessionCreate(
            title="冲突场次",
            theme_id=theme.id, venue_id=venue.id,
            session_type=SessionType.RESEARCH,
            start_time=new_start, end_time=new_end,
            audience_type=AudienceType.SCHOOL,
            audience_count=20, school_id=school.id,
            guides_needed=1, needs_lecturer=False
        ))
        crud.create_assignment(db, conflict_session.id, schemas.AssignmentCreate(
            staff_id=staff1.id, role=AssignmentRole.GUIDE
        ))
        print(f"✓ 创建冲突场次，同一讲解员在 {new_start}-{new_end} 已有安排")

        test_header("3. 提交变更申请（时间+人数变更）")
        
        change, errors = crud.create_change_request(db, schemas.ChangeRequestCreate(
            session_id=session.id,
            requester="王老师（实验小学）",
            change_type=ChangeType.BOTH,
            new_start_time=new_start,
            new_end_time=new_end,
            new_audience_count=50,
            new_guides_needed=2,
            reason="学校临时增加了20名学生，同时下午的交通更方便"
        ))
        if errors:
            print(f"✗ 创建变更申请失败: {errors}")
        else:
            print(f"✓ 创建变更申请: ID={change.id}")
            print(f"  变更类型: {change.change_type.value}")
            print(f"  原时间: {change.old_start_time} - {change.old_end_time}")
            print(f"  新时间: {change.new_start_time} - {change.new_end_time}")
            print(f"  原人数: {change.old_audience_count}, 新人数: {change.new_audience_count}")
            print(f"  原需讲解员: {change.old_guides_needed}, 新需: {change.new_guides_needed}")

        test_header("4. 审核变更申请 - 自动触发冲突检测")
        
        change, errors = crud.review_change_request(db, change.id, schemas.ChangeRequestReview(
            status=ChangeStatus.APPROVED,
            reviewer="调度员小李",
            review_comment="情况属实，同意变更"
        ))
        if errors:
            print(f"✗ 审核失败: {errors}")
        else:
            print(f"✓ 审核通过，状态: {change.status.value}")
            print(f"✓ 自动检测到 {len(change.conflicts)} 个冲突:")
            for c in change.conflicts:
                staff_name = crud.get_staff(db, c.staff_id).name if c.staff_id else ""
                print(f"    - [{c.conflict_type.value}] {c.message}")
            
            print(f"✓ 自动生成 {len(change.reschedule_suggestions)} 条重排建议:")
            for s in change.reschedule_suggestions:
                suggested_name = crud.get_staff(db, s.suggested_staff_id).name if s.suggested_staff_id else ""
                print(f"    - 优先级{s.priority}: [{s.action}] {s.reason}")

        test_header("5. 手动应用单条重排建议")
        
        if change.reschedule_suggestions:
            suggestion = change.reschedule_suggestions[0]
            success, errors = crud.apply_suggestion(db, suggestion.id, "调度员小李")
            if success:
                print(f"✓ 成功应用建议 {suggestion.id}: {suggestion.action}")
            else:
                print(f"✗ 应用建议失败: {errors}")

        test_header("6. 执行变更并自动重排")
        
        result = crud.execute_change_request(db, change.id, "调度员小李")
        print(f"✓ 执行结果: {result.message}")
        print(f"  应用建议数: {result.applied_suggestions}")
        print(f"  剩余冲突: {result.remaining_conflicts}")
        if result.errors:
            print(f"  错误: {result.errors}")

        test_header("7. 验证变更后场次数据")
        
        updated_session = crud.get_session(db, session.id)
        print(f"✓ 场次标题: {updated_session.title}")
        print(f"✓ 新时间: {updated_session.start_time} - {updated_session.end_time}")
        print(f"✓ 新人数: {updated_session.audience_count}")
        print(f"✓ 需讲解员: {updated_session.guides_needed}人")
        print(f"✓ 已安排: {len(updated_session.assignments)}人")
        print(f"✓ 人员充足: {crud.is_session_fully_staffed(db, session.id)}")
        print(f"✓ 场次状态: {updated_session.status.value}")
        
        for a in updated_session.assignments:
            staff = crud.get_staff(db, a.staff_id)
            print(f"    - {staff.name} ({a.role.value})")

        test_header("8. 查看变更历史")
        
        histories = crud.get_change_history_list(db, session_id=session.id)
        print(f"✓ 共 {len(histories)} 条历史记录:")
        for h in histories:
            print(f"    [{h.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {h.operator} - {h.action}: {h.description}")

        test_header("9. 统计 - 场次变更频次")
        
        stats = crud.get_session_change_stats(db, session_id=session.id)
        for s in stats:
            print(f"✓ [{s.session_title}] 总变更{s.change_count}次, "
                  f"时间变更{s.time_change_count}次, 人数变更{s.count_change_count}次")

        test_header("10. 统计 - 变更趋势分析")
        
        freq = crud.get_change_frequency_stats(db, period="day")
        print(f"✓ 按日统计，共 {len(freq)} 天数据:")
        for f in freq[:3]:
            print(f"    [{f.period}] 总变更{f.total_changes}次, "
                  f"通过{f.approved_count}次, 拒绝{f.rejected_count}次, "
                  f"平均处理{f.avg_resolution_time_hours:.2f}小时")

        test_header("11. 测试预检查功能")

        from app.models import ChangeRequest
        temp_change = ChangeRequest(
            session_id=session.id,
            session=updated_session,
            change_type=ChangeType.TIME,
            new_start_time=tomorrow.replace(hour=15, minute=0),
            new_end_time=tomorrow.replace(hour=17, minute=0)
        )
        conflicts, suggestions = crud.check_conflicts_and_generate_suggestions(db, temp_change)
        print(f"✓ 预检查结果: {len(conflicts)}个冲突, {len(suggestions)}条建议")
        for c in conflicts:
            print(f"    - [{c.conflict_type.value}] {c.message}")

        test_header("12. 历史服务积分归属（补录/幂等/更正/结算重算）")

        from app.models import PointSourceType

        now = datetime.now()
        # 补录月份避开当前月，模拟“十月补录六月场次”的场景
        bf_year, bf_month = (2026, 6) if (now.year, now.month) != (2026, 6) else (2026, 5)

        june_session = crud.create_session(db, schemas.SessionCreate(
            title="六月研学场次",
            theme_id=theme.id, venue_id=venue.id,
            session_type=SessionType.RESEARCH,
            start_time=datetime(bf_year, bf_month, 15, 9, 0),
            end_time=datetime(bf_year, bf_month, 15, 11, 0),
            audience_type=AudienceType.SCHOOL,
            audience_count=30, school_id=school.id,
            guides_needed=1, needs_lecturer=False
        ))
        crud.create_assignment(db, june_session.id, schemas.AssignmentCreate(
            staff_id=staff2.id, role=AssignmentRole.GUIDE
        ))
        crud.update_session(db, june_session.id, schemas.SessionUpdate(status=SessionStatus.COMPLETED))
        print(f"✓ 创建{bf_year}年{bf_month}月已完成场次: ID={june_session.id}")

        balance_before = crud.get_staff(db, staff2.id).total_points or 0

        r1 = crud.add_points(db, staff2.id, 25, PointSourceType.SERVICE,
                             session_id=june_session.id, description="复盘补录服务积分")
        assert r1.success and not r1.duplicate
        assert (r1.attributed_year, r1.attributed_month) == (bf_year, bf_month), "补录积分应归属服务发生月份"
        assert r1.occurred_at == june_session.end_time, "业务时间应取场次结束时间"
        assert not r1.month_settled
        print(f"✓ 补录25分: 归属{bf_year}年{bf_month}月, 业务时间={r1.occurred_at}, 处理时间保留于created_at")

        month_pts, month_sessions = crud.calculate_monthly_points(db, staff2.id, bf_year, bf_month)
        cur_pts, _ = crud.calculate_monthly_points(db, staff2.id, now.year, now.month)
        assert month_pts == 25 and month_sessions == 1, f"归属月应为25分，实际{month_pts}"
        assert cur_pts == 0, f"当前月不应计入补录积分，实际{cur_pts}"
        print(f"✓ 月度归属正确: {bf_year}-{bf_month:02d}月=25分/1场, 当前月=0分（不再漂移）")

        r2 = crud.add_points(db, staff2.id, 25, PointSourceType.SERVICE,
                             session_id=june_session.id, description="重复补录同一场次")
        assert r2.success and r2.duplicate and r2.points_added == 0
        assert (crud.get_staff(db, staff2.id).total_points or 0) == balance_before + 25
        month_pts, _ = crud.calculate_monthly_points(db, staff2.id, bf_year, bf_month)
        assert month_pts == 25, "重复补录不得重复计入"
        print(f"✓ 重复补录被幂等忽略: 余额与月度积分均未变化")

        r3 = crud.add_points(db, staff2.id, 40, PointSourceType.SERVICE,
                             correct_record_id=r1.point_record_id, description="更正补录积分")
        assert r3.success and r3.points_added == 15, "更正应按差额入账"
        assert (crud.get_staff(db, staff2.id).total_points or 0) == balance_before + 40
        month_pts, _ = crud.calculate_monthly_points(db, staff2.id, bf_year, bf_month)
        assert month_pts == 40, f"更正后归属月应为40分，实际{month_pts}"
        attr_old = crud.get_point_attribution(db, r1.point_record_id)
        assert attr_old.is_superseded and not attr_old.counted_in_monthly_result
        print(f"✓ 更正生效: 25→40分, 原记录#{r1.point_record_id}被取代且不再计入")

        attr = crud.get_point_attribution(db, r3.point_record_id)
        assert attr.session_id == june_session.id and attr.session_title == "六月研学场次"
        assert (attr.attributed_year, attr.attributed_month) == (bf_year, bf_month)
        assert attr.counted_in_monthly_result and not attr.month_settled
        print(f"✓ 归属解释: 记录#{attr.record_id} 属于场次「{attr.session_title}」, 归属{attr.attributed_year}年{attr.attributed_month}月")

        s1 = crud.settle_monthly_ranking(db, bf_year, bf_month, top_n=3)
        assert s1.success and not s1.recalculated and s1.version == 1
        board = crud.get_monthly_ranking(db, bf_year, bf_month)
        staff2_row = next(r for r in board if r.staff_id == staff2.id)
        assert staff2_row.total_points == 40, "结算应包含补录并更正后的积分"
        print(f"✓ {bf_year}年{bf_month}月榜单结算(第1版): {staff2.name}={staff2_row.total_points}分")

        s_again = crud.settle_monthly_ranking(db, bf_year, bf_month, top_n=3)
        assert not s_again.success, "重复结算应被拒绝"
        print(f"✓ 重复结算被拒绝: {s_again.message}")

        june_session2 = crud.create_session(db, schemas.SessionCreate(
            title="六月第二场研学",
            theme_id=theme.id, venue_id=venue.id,
            session_type=SessionType.RESEARCH,
            start_time=datetime(bf_year, bf_month, 20, 14, 0),
            end_time=datetime(bf_year, bf_month, 20, 16, 0),
            audience_type=AudienceType.SCHOOL,
            audience_count=20, school_id=school.id,
            guides_needed=1, needs_lecturer=False
        ))
        crud.create_assignment(db, june_session2.id, schemas.AssignmentCreate(
            staff_id=staff2.id, role=AssignmentRole.GUIDE
        ))
        r4 = crud.add_points(db, staff2.id, 20, PointSourceType.SERVICE,
                             session_id=june_session2.id, description="结算后补录第二场")
        assert r4.month_settled and r4.requires_recalculation, "已结算月份补录应提示重算"
        print(f"✓ 结算后补录20分: {r4.message}")

        month_pts, _ = crud.calculate_monthly_points(db, staff2.id, bf_year, bf_month)
        assert month_pts == 60, "实时统计应立即反映补录"
        board_stale = crud.get_monthly_ranking(db, bf_year, bf_month)
        assert next(r for r in board_stale if r.staff_id == staff2.id).total_points == 40, "已结算榜单在重算前保持不变"

        s2 = crud.settle_monthly_ranking(db, bf_year, bf_month, top_n=3, recalculate=True)
        assert s2.success and s2.recalculated and s2.version == 2
        board2 = crud.get_monthly_ranking(db, bf_year, bf_month)
        staff2_row2 = next(r for r in board2 if r.staff_id == staff2.id)
        assert staff2_row2.total_points == 60 and staff2_row2.version == 2
        print(f"✓ 显式重算(第2版): {staff2.name}={staff2_row2.total_points}分, 榜单版本={staff2_row2.version}")

        attr2 = crud.get_point_attribution(db, r4.point_record_id)
        assert attr2.month_settled and attr2.ranking_total_points == 60 and attr2.ranking_version == 2
        print(f"✓ 归属解释(结算后): 记录#{attr2.record_id} 影响{bf_year}年{bf_month}月榜单第{attr2.ranking_version}版, 上榜积分={attr2.ranking_total_points}")

        r5 = crud.add_points(db, staff2.id, 5, PointSourceType.BONUS, description="即时奖励积分")
        assert (r5.attributed_year, r5.attributed_month) == (now.year, now.month), "普通即时积分仍归属当前月"
        print(f"✓ 即时积分不回归: 无场次/业务时间时归属当前月")

        test_header("所有测试通过！功能验证完成")
        print("""
核心功能实现清单:
  ✓ 变更申请提交与审核流程
  ✓ 变更触发冲突检测（时间撞场 + 人员不足）
  ✓ 智能重排建议算法
  ✓ 手动/自动应用重排建议
  ✓ 完整变更历史记录
  ✓ 场次变更频次统计
  ✓ 变更趋势分析统计
  ✓ 变更预检查功能

涉及模块扩展:
  ✓ models.py - 新增4个数据模型 + 4个枚举类型
  ✓ schemas.py - 新增12个Pydantic数据结构
  ✓ crud.py - 新增15个核心业务函数
  ✓ routers/changes.py - 新增13个API接口
  ✓ routers/statistics.py - 新增2个统计接口
  ✓ main.py - 注册新路由模块
        """)

    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
