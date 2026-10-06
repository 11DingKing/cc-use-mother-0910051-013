#!/usr/bin/env python3
"""历史服务积分归属修复：端到端场景验证（独立临时库，可重复运行）"""
import os
import sys
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/scenario.db"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine, Base  # noqa: E402
from app import crud, schemas  # noqa: E402
from app.models import (  # noqa: E402
    Staff, Session as SessionModel, Assignment, LevelBadge,
    StaffType, SessionType, SessionStatus, AssignmentRole,
    AudienceType, PointSourceType, PointRecord
)
from app.main import app  # noqa: E402

# main 已完成 create_all + 迁移
client = TestClient(app)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail and not cond else ""))
    assert cond, f"{name}: {detail}"


def setup_data():
    db = SessionLocal()
    # 等级配置
    for lv, mn, mx in [(1, 0, 99), (2, 100, 299), (3, 300, 599), (4, 600, 999), (5, 1000, None)]:
        if not crud.get_level_badge_by_level(db, lv):
            db.add(LevelBadge(level=lv, name=f"L{lv}", badge_name=f"徽章{lv}",
                              min_points=mn, max_points=mx))
    db.commit()

    def make_guide(name):
        return crud.create_staff(db, schemas.StaffCreate(
            name=name, staff_type=StaffType.GUIDE)).id

    g1 = make_guide("甲讲解")
    g2 = make_guide("乙讲解")
    g3 = make_guide("丙讲解")
    g4 = make_guide("丁讲解")

    # 主题/场地（外键）
    from app.models import Theme, Venue
    db.add(Theme(name="主题T", category="x"))
    db.add(Venue(name="场地V", venue_type="展厅"))
    db.commit()

    def make_session(title, start, end, guides):
        s = SessionModel(
            title=title, theme_id=1, venue_id=1,
            session_type=SessionType.RESEARCH,
            start_time=start, end_time=end,
            audience_type=AudienceType.PUBLIC,
            audience_count=20, guides_needed=len(guides),
            status=SessionStatus.COMPLETED
        )
        db.add(s)
        db.flush()
        for g in guides:
            db.add(Assignment(session_id=s.id, staff_id=g, role=AssignmentRole.GUIDE))
        db.commit()
        return s.id

    june = make_session(
        "六月暑期研学场",
        datetime(2026, 6, 20, 9, 0), datetime(2026, 6, 20, 11, 0),
        [g1, g2])  # 甲、乙均参与；甲的服务积分被遗漏，复盘时补录
    october = make_session(
        "十月常规场",
        datetime(2026, 10, 3, 9, 0), datetime(2026, 10, 3, 10, 0),
        [g3])
    # 六月结算前，乙已有该场服务积分（复盘前的正常数据）
    crud.backfill_service_points(db, g2, june, 30, operator="系统",
                                 reason="六月正常服务积分")
    db.close()
    return g1, g2, g3, g4, june, october


def main():
    g1, g2, g3, g4, june_id, oct_id = setup_data()
    db = SessionLocal()

    print("\n[场景0] 十月先给乙的六月场次外的即时背景分（按处理时间）")
    crud.add_points(db, g2, 50, PointSourceType.BONUS, description="十月即时奖励")
    db.close()

    print("\n[场景1] 管理人员先结算六月榜单——此时甲的六月服务积分尚未补录")
    r = client.post("/api/ranking/settle", params={"year": 2026, "month": 6, "top_n": 3})
    check("六月首次结算成功", r.status_code == 200, r.text)
    june_rank = client.get("/api/ranking", params={"year": 2026, "month": 6}).json()
    check("甲讲解不在六月榜单", all(x["staff_id"] != g1 for x in june_rank), str(june_rank))

    print("\n[场景2] 暑期复盘（十月）为甲补录六月场次服务积分 40 分")
    r = client.post(f"/api/sessions/{june_id}/service-points", json={
        "staff_id": g1, "points": 40, "operator": "管理员", "reason": "暑期活动复盘补录"
    })
    check("补录接口成功", r.status_code == 200, r.text)
    body = r.json()
    check("归属到2026年6月", body["service_year"] == 2026 and body["service_month"] == 6,
          str(body))
    check("已结算月被联动调整", body["monthly_affected"]["ranking_status"] == "已调整",
          str(body["monthly_affected"]))
    check("调整给出旧/新名次",
          body["monthly_affected"]["new_rank"] is not None
          and body["monthly_affected"]["old_total_points"] in (None, 0),
          str(body["monthly_affected"]))
    rec_id = body["point_record_id"]

    print("\n[场景3] 六月榜单现在能看到甲，且十月实时统计不含这笔")
    june_rank = client.get("/api/ranking", params={"year": 2026, "month": 6}).json()
    jia = next((x for x in june_rank if x["staff_id"] == g1), None)
    check("甲出现在六月榜单且为40分", jia and jia["total_points"] == 40, str(june_rank))
    check("六月榜单状态=已调整、版本=2", jia["status"] == "已调整" and jia["revision"] == 2,
          str(jia))

    cur = client.get("/api/ranking/current", params={"year": 2026, "month": 10}).json()
    jia_oct = next(x for x in cur if x["staff_id"] == g1)
    check("甲的十月实时月积分不含六月补录", jia_oct["monthly_points"] == 0, str(jia_oct))
    # 总余额含该积分（成长体系累计不变）
    staff_g1 = client.get(f"/api/staff/{g1}").json()
    check("总积分余额包含补录的40分", staff_g1["total_points"] == 40, str(staff_g1))

    june_real = crud.get_staff_point_details(db := SessionLocal(), 2026, 6)
    jia_real = next(x for x in june_real if x.staff_id == g1)
    check("六月实时明细同样能看到40分（与结算口径一致）", jia_real.monthly_points == 40)
    db.close()

    print("\n[场景4] 同一笔补录重复请求——必须幂等，不重复计入")
    bal_before = staff_g1["total_points"]
    r = client.post(f"/api/sessions/{june_id}/service-points", json={
        "staff_id": g1, "points": 40, "operator": "管理员"
    })
    check("重复补录返回 idempotent", r.json()["action"] == "idempotent", r.text)
    staff_after = client.get(f"/api/staff/{g1}").json()
    check("余额不翻倍", staff_after["total_points"] == bal_before == 40,
          f"{staff_after['total_points']}")
    db = SessionLocal()
    valid_recs = [x for x in crud.get_point_records(db, staff_id=g1, include_voided=True)]
    check("有效服务积分仍只有1笔",
          len([x for x in valid_recs if not x.is_voided and x.source_type == PointSourceType.SERVICE]) == 1)
    db.close()
    june_rank2 = client.get("/api/ranking", params={"year": 2026, "month": 6}).json()
    check("重复补录不产生新版本",
          next(x for x in june_rank2 if x["staff_id"] == g1)["revision"] == 2)

    print("\n[场景5] 更正为 25 分——旧记录作废保留审计，榜单联动重算")
    r = client.post(f"/api/sessions/{june_id}/service-points", json={
        "staff_id": g1, "points": 25, "operator": "管理员", "reason": "核对时长后更正"
    })
    check("更正成功", r.status_code == 200 and r.json()["action"] == "corrected", r.text)
    db = SessionLocal()
    recs = crud.get_point_records(db, staff_id=g1, include_voided=True)
    valid = [x for x in recs if not x.is_voided]
    voided = [x for x in recs if x.is_voided]
    check("旧记录作废保留、新记录生效", len(voided) == 1 and len(valid) == 1 and valid[0].points == 25)
    check("新记录挂 replaces_id 且 fact_key 已迁移",
          valid[0].replaces_id == voided[0].id and valid[0].fact_key and voided[0].fact_key is None)
    check("作废记录保留处理时间/原因审计",
          voided[0].voided_at is not None and "更正" in (voided[0].void_reason or ""))
    check("余额=25（差额回退15）", (client.get(f"/api/staff/{g1}").json())["total_points"] == 25)
    db.close()
    june_rank3 = client.get("/api/ranking", params={"year": 2026, "month": 6}).json()
    jia3 = next(x for x in june_rank3 if x["staff_id"] == g1)
    check("六月榜单更正为25分、版本=3", jia3["total_points"] == 25 and jia3["revision"] == 3, str(jia3))

    print("\n[场景6] 已结算月重复点结算（不带 force_recalculate）必须被拒绝")
    r = client.post("/api/ranking/settle", params={"year": 2026, "month": 6})
    check("重复结算返回400", r.status_code == 400, r.text)
    r = client.post("/api/ranking/settle",
                    params={"year": 2026, "month": 6, "force_recalculate": True})
    check("显式重算成功", r.status_code == 200 and r.json()["action"] == "recalculated", r.text)
    check("台账未变则0人变化、版本停留3",
          r.json()["changed_staff"] == [] and r.json()["revision"] == 3, r.text)

    print("\n[场景7] 调整审计可查")
    adj = client.get("/api/ranking/adjustments", params={"year": 2026, "month": 6}).json()
    check("存在补录/更正调整审计", len(adj) >= 2 and all(a["reason"] == "补录更正" for a in adj),
          str(adj))

    print("\n[场景8] 普通即时积分按处理时间归属，不污染六月、不产生榜单调整")
    r = client.post(f"/api/staff/{g1}/points",
                    params={"points": 70, "source_type": "BONUS", "description": "十月专项奖励"})
    check("即时积分发放成功", r.status_code == 200, r.text)
    oct_cur = client.get("/api/ranking/current", params={"year": 2026, "month": 10}).json()
    jia_oct2 = next(x for x in oct_cur if x["staff_id"] == g1)
    check("十月实时含70分即时奖励", jia_oct2["monthly_points"] == 70, str(jia_oct2))
    june_final = client.get("/api/ranking", params={"year": 2026, "month": 6}).json()
    check("六月已结算结果不受即时积分影响（仍25）",
          next(x for x in june_final if x["staff_id"] == g1)["total_points"] == 25)

    print("\n[场景9] 积分归属可解释：服务事实 + 月度结果")
    attr = client.get(f"/api/points/{rec_id}/attribution")
    # rec_id 指向的可能是已作废的首次记录
    a = attr.json()
    check("归属接口可查（含作废记录）", attr.status_code == 200 and a["is_voided"] is True, attr.text)
    check("能说出对应场次事实", a["session_id"] == june_id and "六月" in (a["session_title"] or ""),
          str(a))
    check("归属依据=服务事实", "服务事实" in a["attribution_basis"], a["attribution_basis"])
    check("保留处理时间与操作人审计", a["created_at"] and a["operator"] == "管理员", str(a))
    db = SessionLocal()
    newest = crud.get_point_records(db, staff_id=g1)[0]
    db.close()
    attr2 = client.get(f"/api/points/{newest.id}/attribution").json()
    check("有效记录指向已调整的六月结果",
          attr2["monthly_impacts"] and attr2["monthly_impacts"][0]["ranking_status"] == "已调整",
          str(attr2["monthly_impacts"]))
    # 即时积分的解释
    db = SessionLocal()
    bonus_rec = next(x for x in crud.get_point_records(db, staff_id=g1)
                     if x.source_type == PointSourceType.BONUS and x.points == 70)
    db.close()
    attr3 = client.get(f"/api/points/{bonus_rec.id}/attribution").json()
    check("即时积分归属依据=处理时间", "处理时间" in attr3["attribution_basis"], str(attr3))

    print("\n[场景10] 既有成长记录（勋章）不回归；服务积分撤销可重建")
    db = SessionLocal()
    # g4 通过两次即时奖励跨级升级，获得两枚勋章历史
    crud.add_points(db, g4, 300, PointSourceType.BONUS, description="升级测试一")
    crud.add_points(db, g4, 700, PointSourceType.BONUS, description="升级测试二")
    badges_before = len(crud.get_staff_badges(db, g4))
    check("跨级获得多枚勋章历史", badges_before >= 2, str(badges_before))

    # 给 g4 单独安排一个十月场次
    oct2 = SessionModel(
        title="十月第二场", theme_id=1, venue_id=1,
        session_type=SessionType.RESEARCH,
        start_time=datetime(2026, 10, 5, 9, 0), end_time=datetime(2026, 10, 5, 10, 0),
        audience_type=AudienceType.PUBLIC, audience_count=10, guides_needed=1,
        status=SessionStatus.COMPLETED)
    db.add(oct2); db.flush()
    db.add(Assignment(session_id=oct2.id, staff_id=g4, role=AssignmentRole.GUIDE))
    db.commit()
    oct2_id = oct2.id
    db.close()

    r1 = client.post(f"/api/sessions/{oct2_id}/service-points",
                     json={"staff_id": g4, "points": 30}).json()
    check("十月场次补录30成功", r1["action"] == "created", str(r1))
    check("十月未结算，monthly_affected=未结算",
          r1["monthly_affected"]["ranking_status"] == "未结算", str(r1))
    cur_before = next(x for x in client.get("/api/ranking/current",
                       params={"year": 2026, "month": 10}).json()
                      if x["staff_id"] == g4)["monthly_points"]
    check("撤销前十月实时含服务30", cur_before == 1030, str(cur_before))

    r2 = client.post(f"/api/sessions/{oct2_id}/service-points",
                     json={"staff_id": g4, "points": 0}).json()
    check("更正为0=撤销", r2["action"] == "corrected", str(r2))
    db2 = SessionLocal()
    recs3 = crud.get_point_records(db2, staff_id=g4, include_voided=True)
    check("撤销后无有效服务积分",
          all(x.is_voided or x.source_type != PointSourceType.SERVICE for x in recs3))
    db2.close()
    cur_after = next(x for x in client.get("/api/ranking/current",
                      params={"year": 2026, "month": 10}).json()
                     if x["staff_id"] == g4)["monthly_points"]
    check("撤销后十月实时回落1000（即时奖励仍在）", cur_after == 1000, str(cur_after))

    # 撤销后可重新补录（更正链延续，不撞唯一键）
    r3 = client.post(f"/api/sessions/{oct2_id}/service-points",
                     json={"staff_id": g4, "points": 20}).json()
    check("撤销后重新补录20成功", r3["action"] == "created", str(r3))
    db2 = SessionLocal()
    valid_svc = [x for x in crud.get_point_records(db2, staff_id=g4)
                 if x.source_type == PointSourceType.SERVICE]
    check("重新补录后仅1笔有效服务积分20", len(valid_svc) == 1 and valid_svc[0].points == 20)
    db2.close()

    db = SessionLocal()
    badges_after = len(crud.get_staff_badges(db, g4))
    check("勋章成长记录未被删除", badges_after == badges_before,
          f"{badges_before} -> {badges_after}")
    db.close()

    print("\n[场景11] 评价触发服务积分：按场次月归属，重复评价不重复发服务分")
    # 新建一个未结算月份之外的七月场次并评价
    db = SessionLocal()
    jul = SessionModel(
        title="七月补评价场", theme_id=1, venue_id=1,
        session_type=SessionType.RESEARCH,
        start_time=datetime(2026, 7, 5, 9, 0), end_time=datetime(2026, 7, 5, 10, 0),
        audience_type=AudienceType.PUBLIC, audience_count=10, guides_needed=1,
        status=SessionStatus.COMPLETED)
    db.add(jul); db.flush()
    db.add(Assignment(session_id=jul.id, staff_id=g1, role=AssignmentRole.GUIDE))
    db.commit()
    jul_id = jul.id
    db.close()
    client.post("/api/reviews", json={"session_id": jul_id, "reviewer_name": "观众A",
                                      "reviewer_type": "公众", "rating": 5})
    db = SessionLocal()
    svc = [x for x in crud.get_point_records(db, staff_id=g1, session_id=jul_id)
           if x.source_type == PointSourceType.SERVICE]
    check("首条评价发放服务积分并归属7月", len(svc) == 1 and svc[0].service_month == 7, str(svc))
    db.close()
    client.post("/api/reviews", json={"session_id": jul_id, "reviewer_name": "观众B",
                                      "reviewer_type": "公众", "rating": 3})
    db = SessionLocal()
    svc2 = [x for x in crud.get_point_records(db, staff_id=g1, include_voided=True)
            if x.session_id == jul_id and x.source_type == PointSourceType.SERVICE]
    check("第二条评价不新增第二笔事实（旧笔作废或仅1笔）",
          len([x for x in svc2 if not x.is_voided]) == 1, str([(x.points, x.is_voided) for x in svc2]))
    db.close()

    print("\n[场景12] 场次跨月改期：服务积分随业务事实迁月，已结算月联动调整")
    db = SessionLocal()
    aug = SessionModel(
        title="八月待改期场", theme_id=1, venue_id=1,
        session_type=SessionType.RESEARCH,
        start_time=datetime(2026, 8, 28, 9, 0), end_time=datetime(2026, 8, 28, 10, 0),
        audience_type=AudienceType.PUBLIC, audience_count=10, guides_needed=1,
        status=SessionStatus.COMPLETED)
    db.add(aug); db.flush()
    db.add(Assignment(session_id=aug.id, staff_id=g2, role=AssignmentRole.GUIDE))
    db.commit()
    aug_id = aug.id
    db.close()
    client.post(f"/api/sessions/{aug_id}/service-points",
                json={"staff_id": g2, "points": 35})
    # 先结算八月（35 在八月榜单）
    s_aug = client.post("/api/ranking/settle", params={"year": 2026, "month": 8}).json()
    check("八月结算成功", s_aug["success"])
    aug_row = next(x for x in client.get("/api/ranking", params={"year": 2026, "month": 8}).json()
                   if x["staff_id"] == g2)
    check("乙八月榜单含35", aug_row["total_points"] == 35, str(aug_row))
    # 改期到 9 月 2 日
    upd = client.put(f"/api/sessions/{aug_id}", json={
        "start_time": "2026-09-02T09:00:00",
        "end_time": "2026-09-02T10:00:00"
    })
    check("场次改期成功", upd.status_code == 200, upd.text)
    db = SessionLocal()
    pts, mon = crud.calculate_monthly_points(db, g2, 2026, 8), None
    check("八月不再含该35分", pts[0] == 0, str(pts))
    sep = crud.calculate_monthly_points(db, g2, 2026, 9)
    check("九月含迁来的35分", sep[0] == 35, str(sep))
    db.close()
    aug_after = next(x for x in client.get("/api/ranking", params={"year": 2026, "month": 8}).json()
                     if x["staff_id"] == g2)
    check("八月已结算榜单联动移除35并升版",
          aug_after["total_points"] == 0 and aug_after["revision"] == 2 and aug_after["status"] == "已调整",
          str(aug_after))
    adj_aug = client.get("/api/ranking/adjustments", params={"year": 2026, "month": 8}).json()
    check("八月留有'场次时间变更'审计", any(a["reason"] == "场次时间变更" for a in adj_aug), str(adj_aug))

    print("\n" + "=" * 60)
    print(f"结果: {len(PASS)} 通过, {len(FAIL)} 失败")
    if FAIL:
        print("失败项:", FAIL)
        return 1
    print("🎉 历史服务积分归属全部场景验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
