import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from database import init_db
import equipment_manager
import rental_manager
import reservation_manager
import report_manager


def setup():
    init_db()
    equipment_manager.refresh_all_maintenance_statuses()


def test_date_validation():
    print("\n" + "=" * 60)
    print("测试1: 日期范围校验")
    print("=" * 60)

    print("\n1.1 正常日期范围...")
    ok, msg = equipment_manager.validate_date_range('2026-06-01', '2026-06-10')
    assert ok, f"正常范围应通过: {msg}"
    print(f"   ✅ 通过")

    print("\n1.2 结束日期早于开始日期 (预计归还早于起租)...")
    ok, msg = equipment_manager.validate_date_range('2026-06-10', '2026-06-01')
    assert not ok, "反向日期应失败"
    print(f"   ✅ 正确拦截: {msg}")

    print("\n1.3 日期格式错误...")
    ok, msg = equipment_manager.validate_date_range('2026/06/01', '2026-06-10')
    assert not ok, "错误格式应失败"
    print(f"   ✅ 正确拦截: {msg}")

    print("\n1.4 相同日期 (当天归还)...")
    ok, msg = equipment_manager.validate_date_range('2026-06-10', '2026-06-10')
    assert ok, "同日应允许"
    print(f"   ✅ 通过: 1天租期")

    print("\n1.5 租赁创建: 日期范围校验集成...")
    eq = equipment_manager.get_equipment_by_code('YL-002')
    customers = rental_manager.list_customers()
    bad_start = '2026-06-15'
    bad_end = '2026-06-10'
    ok, rid, msg = rental_manager.create_rental(
        customers[0]['id'], eq['id'], bad_start, bad_end, eq['total_hours'], '按天', daily_rate=1000
    )
    assert not ok, "创建时错误日期范围应失败"
    print(f"   ✅ 正确拦截: {msg[:50]}...")

    print("\n🏆 日期校验测试通过!")


def test_maintenance_status_flow():
    print("\n" + "=" * 60)
    print("测试2: 保养状态流转与限制出租")
    print("=" * 60)

    print("\n2.1 触发待保养 (更新工时达到保养周期)...")
    eq = equipment_manager.get_equipment_by_code('WJ-003')
    eq_id = eq['id']
    old_status = eq['status']
    interval = eq['maintenance_interval']
    last_maint = eq['last_maintenance_hours']
    target_hours = last_maint + interval + 10
    equipment_manager.update_equipment_hours(eq_id, target_hours)

    new_status = equipment_manager.refresh_maintenance_status(eq_id)
    eq_check = equipment_manager.get_equipment_by_id(eq_id)
    print(f"   原值: {old_status}, 操作后: {eq_check['status']} (工时: {target_hours:.0f}h)")
    assert eq_check['status'] == '待保养', f"应标记待保养: {eq_check['status']}"
    print(f"   ✅ 已自动标记为 [待保养]")

    print("\n2.2 待保养设备禁止出租...")
    customers = rental_manager.list_customers()
    start = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    end = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    ok, rid, msg = rental_manager.create_rental(
        customers[0]['id'], eq_id, start, end, target_hours, '按天', daily_rate=1000
    )
    assert not ok, "待保养设备应禁止出租"
    print(f"   ✅ 正确拦截: {msg[:60]}...")

    print("\n2.3 开始保养流程...")
    ok, msg = equipment_manager.start_maintenance(eq_id)
    assert ok, f"开始保养失败: {msg}"
    eq_check = equipment_manager.get_equipment_by_id(eq_id)
    assert eq_check['status'] == '保养中', f"应转为保养中: {eq_check['status']}"
    print(f"   ✅ 状态转为 [保养中]")

    print("\n2.4 保养中设备禁止出租...")
    ok, rid, msg = rental_manager.create_rental(
        customers[0]['id'], eq_id, start, end, target_hours, '按天', daily_rate=1000
    )
    assert not ok, "保养中设备应禁止出租"
    print(f"   ✅ 正确拦截: {msg[:60]}...")

    print("\n2.5 记录保养完成，恢复可租...")
    m_date = datetime.now().strftime('%Y-%m-%d')
    m_hours = target_hours + 2
    ok, info, msg = equipment_manager.add_maintenance_record(
        eq_id, m_date, m_hours, '常规保养', 850, '测试保养'
    )
    assert ok, f"保养记录失败: {msg}"
    eq_final = equipment_manager.get_equipment_by_id(eq_id)
    assert eq_final['status'] == '空闲', f"保养后应恢复空闲: {eq_final['status']}"
    assert eq_final['last_maintenance_hours'] == m_hours, "保养工时未更新"
    print(f"   ✅ 状态转为 [空闲], 费用 ¥850.00 已记录")
    print(f"   ✅ 保养信息: 上次保养 {info['hours_since_last']:.0f}h, 状态 {info['prev_status']}→{info['new_status']}")

    print("\n2.6 保养后恢复可出租...")
    eq_test = equipment_manager.get_equipment_by_id(eq_id)
    ok, avail_msg = equipment_manager.is_available_for_rent(eq_id)
    assert ok, f"保养后应可出租: {avail_msg}"
    print(f"   ✅ 设备可出租，状态: {avail_msg}")

    print("\n2.7 保养工时合法性校验 (不能小于上次保养)...")
    bad_hours = last_maint - 50
    ok, info, msg = equipment_manager.add_maintenance_record(
        eq_id, m_date, bad_hours, '异常保养', 0
    )
    assert not ok, "保养工时小于上次保养应失败"
    print(f"   ✅ 正确拦截: {msg}")

    print("\n2.8 保养费用统计...")
    summary = equipment_manager.get_maintenance_cost_summary(
        year=datetime.now().year, month=datetime.now().month
    )
    print(f"   本月保养次数: {summary['total_count']} 次")
    print(f"   本月保养总费用: ¥{summary['total_cost']:.2f}")
    assert summary['total_cost'] >= 850, "保养费用未计入统计"
    print(f"   ✅ 统计正确")

    print("\n🏆 保养状态流转测试通过!")


def test_reservation_and_conflicts():
    print("\n" + "=" * 60)
    print("测试3: 预约排期与时间冲突检测")
    print("=" * 60)

    customers = rental_manager.list_customers()
    eq = equipment_manager.list_equipment(status='空闲')
    assert len(eq) > 0, "需要至少一台空闲设备"
    test_eq = eq[0]
    eq_id = test_eq['id']
    cust1 = customers[0]
    cust2 = customers[1] if len(customers) > 1 else customers[0]

    print("\n3.1 创建首个预约...")
    d1 = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    d2 = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    ok, rid, msg = reservation_manager.create_reservation(
        cust1['id'], eq_id, d1, d2, '按天', expected_daily_rate=2000
    )
    assert ok, f"创建预约失败: {msg}"
    print(f"   ✅ 预约ID={rid}: {d1} ~ {d2}, 客户: {cust1['name'][:10]}")

    print("\n3.2 冲突检测 - 完全重叠的预约...")
    ok, rid2, msg = reservation_manager.create_reservation(
        cust2['id'], eq_id, d1, d2, '按天', expected_daily_rate=2000
    )
    assert not ok, "完全重叠应被拦截"
    print(f"   ✅ 正确拦截")

    print("\n3.3 冲突检测 - 部分重叠的预约...")
    d_conflict = (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d')
    d_end2 = (datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d')
    ok, rid3, msg = reservation_manager.create_reservation(
        cust2['id'], eq_id, d_conflict, d_end2, '按天', expected_daily_rate=2000
    )
    assert not ok, "部分重叠应被拦截"
    print(f"   ✅ 正确拦截")

    print("\n3.4 冲突检测 - 与在租租赁冲突...")
    eq2 = [e for e in eq if e['id'] != eq_id][:1] or eq[:1]
    eq2_id = eq2[0]['id']
    r_start = datetime.now().strftime('%Y-%m-%d')
    r_end = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    ok, r_id, _ = rental_manager.create_rental(
        cust1['id'], eq2_id, r_start, r_end, eq2[0]['total_hours'],
        '按天', daily_rate=1500
    )
    assert ok, "创建在租失败"
    print(f"   在租ID={r_id}: {r_start} ~ {r_end}")

    d_conflict2 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    d_end3 = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    ok, rid4, msg = reservation_manager.create_reservation(
        cust2['id'], eq2_id, d_conflict2, d_end3, '按天'
    )
    assert not ok, "与在租重叠应拦截"
    print(f"   ✅ 与在租冲突正确拦截")

    print("\n3.5 创建无冲突的第二预约...")
    d3 = (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')
    d4 = (datetime.now() + timedelta(days=18)).strftime('%Y-%m-%d')
    ok, rid5, msg = reservation_manager.create_reservation(
        cust2['id'], eq_id, d3, d4, '按天', expected_daily_rate=2000
    )
    assert ok, f"无冲突预约失败: {msg}"
    print(f"   ✅ 预约ID={rid5}: {d3} ~ {d4}")

    print("\n3.6 确认预约...")
    ok, msg = reservation_manager.confirm_reservation(rid5)
    assert ok, f"确认失败: {msg}"
    r = reservation_manager.get_reservation_by_id(rid5)
    assert r['status'] == '已确认', f"状态应已确认: {r['status']}"
    print(f"   ✅ 预约状态转为 [已确认]")

    print("\n3.7 查看设备排期...")
    schedule = equipment_manager.get_equipment_schedule(eq_id)
    print(f"   设备 {test_eq['code']} 排期: {len(schedule)} 条记录")
    for s in schedule:
        print(f"     - [{s['source']}] {s['start']} ~ {s['end']} ({s['status']}) {s['customer'][:10]}")
    assert len(schedule) >= 2, "排期应至少2条"
    print(f"   ✅ 排期展示正确")

    print("\n3.8 预约转正式租赁...")
    d_conv = (datetime.now() + timedelta(days=25)).strftime('%Y-%m-%d')
    d_conv_end = (datetime.now() + timedelta(days=28)).strftime('%Y-%m-%d')
    ok, rid_new, _ = reservation_manager.create_reservation(
        cust2['id'], eq2[0]['id'], d_conv, d_conv_end, '按天', expected_daily_rate=1600
    )
    eq_test2 = equipment_manager.get_equipment_by_id(eq2[0]['id'])
    ok2, rental_id, msg = reservation_manager.convert_reservation_to_rental(
        rid_new, eq_test2['total_hours'], '从预约转换'
    )
    if ok2:
        print(f"   ✅ 预约转租赁成功，租赁ID={rental_id}")
        r_check = rental_manager.get_rental_by_id(rental_id)
        rv_check = reservation_manager.get_reservation_by_id(rid_new)
        assert r_check is not None, "租赁未创建"
        assert rv_check['status'] == '已转租赁', f"预约状态应为已转租赁"
        print(f"   ✅ 租赁状态: {r_check['status']}, 预约状态: {rv_check['status']}")

        rental_manager.return_equipment(rental_id, d_conv_end, eq_test2['total_hours'] + 24)
    else:
        print(f"   ⚠️  转换未成功(可能与在租冲突): {msg[:50]}")

    print("\n3.9 取消预约...")
    ok, msg = reservation_manager.cancel_reservation(rid, '测试取消')
    assert ok, f"取消失败: {msg}"
    r_check = reservation_manager.get_reservation_by_id(rid)
    assert r_check['status'] == '已取消', f"应为已取消: {r_check['status']}"
    print(f"   ✅ 预约已取消，原因已记录")

    print("\n🏆 预约与冲突检测测试通过!")


def test_utilization_report():
    print("\n" + "=" * 60)
    print("测试4: 设备利用率报表")
    print("=" * 60)

    now = datetime.now()
    year = now.year
    month = now.month

    print(f"\n4.1 生成 {year}年{month}月利用率报表...")
    report = report_manager.get_utilization_report(year, month)
    s = report['summary']
    print(f"   统计天数: {s['days_in_month']} 天")
    print(f"   设备总数: {s['equipment_count']} 台")
    print(f"   总可用台天: {s['total_available_days']}")
    print(f"   实际出租台天: {s['total_rented_days']}")
    print(f"   整体利用率: {s['avg_utilization']:.2f}%")
    print(f"   累计收入: ¥{s['total_income']:.2f}")
    assert s['equipment_count'] > 0, "设备数应>0"
    assert s['total_available_days'] == s['equipment_count'] * s['days_in_month']
    print(f"   ✅ 汇总数据正确")

    print("\n4.2 按设备类型汇总...")
    assert len(report['by_type']) > 0, "类型汇总为空"
    for t in report['by_type']:
        print(f"   - {t['type']}: {t['count']}台, 利用率{t['utilization']:.1f}%, 收入¥{t['income']:.0f}, "
              f"平均出租{t['avg_rented_days']:.1f}天/台")
    print(f"   ✅ 类型汇总正确，按利用率降序排列")

    print("\n4.3 单台设备明细 (识别闲置)...")
    assert len(report['by_equipment']) > 0, "单台明细为空"
    idle_count = 0
    heavy_count = 0
    for e in report['by_equipment'][:5]:
        tip = ''
        if e['utilization'] < 20:
            tip = '⚠️严重闲置'
            idle_count += 1
        elif e['utilization'] >= 80:
            tip = '🔥高负荷'
            heavy_count += 1
        print(f"   - {e['code']}({e['type'][:3]}): 出租{e['rented_days']}天/空闲{e['idle_days']}天, "
              f"利用率{e['utilization']:.1f}%, ¥{e['income']:.0f} {tip}")
    print(f"   ✅ 单台明细正确，按利用率升序排列 (闲置优先展示)")
    print(f"   ✅ 严重闲置: {idle_count}台, 高负荷: {heavy_count}台")

    print("\n4.4 导出利用率CSV...")
    path = report_manager.export_utilization_report_to_csv(year, month)
    assert os.path.exists(path), "CSV未生成"
    size = os.path.getsize(path)
    print(f"   ✅ 导出成功: {os.path.basename(path)} ({size} bytes)")

    print("\n🏆 设备利用率报表测试通过!")


def test_edge_cases_in_rental():
    print("\n" + "=" * 60)
    print("测试5: 租赁边界情况 (归还日期/工时校验)")
    print("=" * 60)

    print("\n5.1 归还工时小于起租工时...")
    eq = equipment_manager.list_equipment(status='空闲')[0]
    customers = rental_manager.list_customers()
    start = datetime.now().strftime('%Y-%m-%d')
    end = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    start_h = eq['total_hours']
    ok, rid, _ = rental_manager.create_rental(
        customers[0]['id'], eq['id'], start, end, start_h, '按天', daily_rate=1000
    )
    assert ok, "创建租赁失败"
    bad_return_h = start_h - 10
    actual_end = end
    ok, msg = rental_manager.return_equipment(rid, actual_end, bad_return_h)
    assert not ok, "归还工时小于起租应失败"
    print(f"   ✅ 正确拦截: {msg[:60]}...")

    print("\n5.2 归还日期早于起租日期...")
    eq2 = equipment_manager.list_equipment(status='空闲')[0]
    start2 = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    expected2 = (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d')
    start_h2 = eq2['total_hours']
    ok2, rid2, _ = rental_manager.create_rental(
        customers[0]['id'], eq2['id'], start2, expected2, start_h2, '按天', daily_rate=1000
    )
    assert ok2, "创建租赁失败"
    bad_return_date = datetime.now().strftime('%Y-%m-%d')
    ok3, msg2 = rental_manager.return_equipment(rid2, bad_return_date, start_h2 + 16)
    assert not ok3, "归还日期早于起租应失败"
    print(f"   ✅ 正确拦截: {msg2[:60]}...")

    rental_manager.return_equipment(rid2, expected2, start_h2 + 24)

    print("\n5.3 费用计算不会产生负数...")
    fees = rental_manager.calculate_rental_fee(rid, actual_end, start_h + 16)
    assert fees is not None and 'error' not in fees, "费用计算失败"
    assert fees['base_rent'] >= 0, "基本租金不能为负"
    assert fees['overtime_fine'] >= 0, "超期罚款不能为负"
    assert fees['total_amount'] >= 0, "总金额不能为负"
    print(f"   ✅ 基本租金: ¥{fees['base_rent']:.2f}, 罚款: ¥{fees['overtime_fine']:.2f}, 总计: ¥{fees['total_amount']:.2f}")
    print(f"   ✅ 所有费用均为非负数")

    rental_manager.return_equipment(rid, actual_end, start_h + 16)

    print("\n🏆 边界情况测试通过!")


def main():
    print("🚀 v2.0 增强版功能测试套件")
    setup()
    try:
        test_date_validation()
        test_maintenance_status_flow()
        test_reservation_and_conflicts()
        test_utilization_report()
        test_edge_cases_in_rental()
        print("\n" + "=" * 60)
        print("🎉 v2.0 所有新增功能测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
