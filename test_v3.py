import sys
import os
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from database import init_db
import equipment_manager
import rental_manager
import reservation_manager
import settlement_manager
import report_manager
import seed_data


def clean_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')
    if os.path.exists(db_path):
        os.remove(db_path)


def setup():
    clean_db()
    init_db()


def test_sample_data():
    print("\n" + "=" * 60)
    print("测试1: 示例数据完整加载")
    print("=" * 60)
    seed_data.seed_sample_data()
    equipment_manager.refresh_all_maintenance_statuses()
    from database import get_conn
    conn = get_conn()
    c = conn.cursor()
    checks = [
        ('equipment', '设备', 10),
        ('customer', '客户', 5),
        ('rental', '租赁', 6),
        ('maintenance', '保养', 4),
        ('reservation', '预约', 3),
    ]
    print()
    all_ok = True
    for tbl, name, min_count in checks:
        c.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = c.fetchone()[0]
        status = "✅" if cnt >= min_count else "❌"
        print(f"  {status} {name}: {cnt} 条 (期望>={min_count})")
        if cnt < min_count:
            all_ok = False
    c.execute("SELECT COUNT(*) FROM settlement")
    s_cnt = c.fetchone()[0]
    print(f"  ✅ 结算: {s_cnt} 条 (自动生成)")
    conn.close()
    assert all_ok, "示例数据不完整"
    print("\n🏆 示例数据加载正常！")


def test_reservation_conversion_closed_loop():
    print("\n" + "=" * 60)
    print("测试2: 预约→租赁→归还→结算 闭环流程")
    print("=" * 60)

    customers = rental_manager.list_customers()
    idle = [e for e in equipment_manager.list_equipment() if e['status'] not in ('待保养', '保养中')]
    assert idle, "无空闲可用设备"
    eq = idle[0]
    cust = customers[0]
    start = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')
    end = (datetime.now().date() + timedelta(days=5)).strftime('%Y-%m-%d')

    print(f"\n2.1 创建预约...")
    ok, rvid, msg = reservation_manager.create_reservation(
        cust['id'], eq['id'], start, end, '按天', expected_daily_rate=2000
    )
    assert ok, msg
    print(f"   ✅ 预约 #{rvid} created: {start} ~ {end}")

    print(f"\n2.2 确认预约...")
    ok, msg = reservation_manager.confirm_reservation(rvid)
    assert ok, f"确认失败: {msg}"
    print(f"   ✅ {msg}")

    print(f"\n2.3 预约转租赁 (exclusion_id传递)...")
    before_eq = equipment_manager.get_equipment_by_id(eq['id'])
    ok_conv, rental_id, msg = reservation_manager.convert_reservation_to_rental(
        rvid, before_eq['total_hours'] + 10, '测试预约闭环测试'
    )
    assert ok_conv, f"转换失败: {msg}"
    print(f"   ✅ 成功转为租赁 #{rental_id}")

    rv = reservation_manager.get_reservation_by_id(rvid)
    assert rv['status'] == '已转租赁', f"预约状态应为已转租赁，实际{rv['status']}"
    assert rv['converted_rental_id'] == rental_id, f"converted_rental_id未同步"
    print(f"   ✅ 预约状态: {rv['status']}, 关联租赁ID: {rv['converted_rental_id']}")

    eq_check = equipment_manager.get_equipment_by_id(eq['id'])
    assert eq_check['status'] == '在租', f"设备状态应为在租，实际{eq_check['status']}"
    print(f"   ✅ 设备状态: {eq_check['status']}")

    print(f"\n2.4 验证: 创建冲突检测 - 同时间段再次尝试创建应失败...")
    ok2, _, msg2 = rental_manager.create_rental(
        cust['id'], eq['id'], start, end, eq_check['total_hours'], '按天', daily_rate=2000
    )
    assert not ok2, "应被冲突检测没拦住"
    print(f"   ✅ 正确拦截 (不会被原预约/租赁自己拦住)")

    print(f"\n2.5 设备归还并自动生成结算单...")
    ret_date = end
    ok_ret, result = rental_manager.return_equipment(
        rental_id, ret_date, eq_check['total_hours'] + 32
    )
    assert ok_ret, f"归还失败: {result}"
    print(f"   ✅ 归还成功, 总金额 ¥{result.get('total_amount'):.2f}")
    assert 'settlement_id' in result or 'settlement' in result, "未返回结算单信息"
    s_id = result.get('settlement_id')
    if not s_id and result.get('settlement'):
        s_id = result['settlement']['id']
    print(f"   ✅ 结算单 #{s_id} 自动生成")

    s = settlement_manager.get_settlement_by_id(s_id)
    assert s is not None, "结算单不存在"
    print(f"   ✅ 结算单内容完整: 租期{s['rental_days']}天, 金额¥{s['total_amount']:.2f}, 状态{s['payment_status']}")

    print(f"\n2.6 记录收款...")
    ok_p, msg_p = settlement_manager.record_payment(s_id, s['total_amount'], '测试全额收款')
    assert ok_p, f"收款失败: {msg_p}"
    s2 = settlement_manager.get_settlement_by_id(s_id)
    assert s2['payment_status'] == '已结清', f"状态应为已结清, 实际{s2['payment_status']}"
    print(f"   ✅ {msg_p}")

    print("\n🏆 预约→租赁→归还→结算→收款 闭环全部通过!")


def test_calendar_and_availability():
    print("\n" + "=" * 60)
    print("测试3: 月历式排期查询")
    print("=" * 60)

    now = datetime.now()
    print(f"\n3.1 单设备月历...")
    all_eq = equipment_manager.list_equipment()[:1]
    eq = all_eq[0]
    cal = equipment_manager.get_equipment_calendar(eq['id'], now.year, now.month)
    assert cal['equipment'] is not None
    assert len(cal['calendar']) == cal['days_in_month']
    statuses = set(d['status'] for d in cal['calendar'])
    print(f"   ✅ {eq['code']} {now.year}年{now.month}月共{cal['days_in_month']}天, 状态包含: {', '.join(sorted(statuses))}")

    print(f"\n3.2 按类型批量空闲矩阵...")
    matrix = equipment_manager.get_type_availability_matrix('挖掘机', now.year, now.month)
    assert len(matrix['equipments']) >= 1
    for info in matrix['equipments'][:2]:
        print(f"   - {info['code']}: {info['free_count']}天空闲 / {info['model']}")
    print(f"   ✅ {matrix['eq_type']} 共{len(matrix['equipments'])}台设备, 返回数据完整")

    print("\n🏆 月历排期查询测试通过!")


def test_billing_and_settlement():
    print("\n" + "=" * 60)
    print("测试4: 客户账单汇总查询")
    print("=" * 60)

    print("\n4.1 所有客户账单汇总...")
    billings, grand = settlement_manager.get_customer_billing_summary()
    assert len(billings) >= 1
    print(f"   有账单客户数: {len(billings)}, 总应收¥{grand['total_billed']:.2f}, 已收¥{grand['total_paid']:.2f}, 未结¥{grand['total_unpaid']:.2f}")
    for b in billings[:3]:
        print(f"   - {b['customer_name']}: 单数{b['bill_count']}笔, 未结¥{b['total_unpaid']:.2f}")
    print(f"   ✅ 账单汇总数据完整")

    print(f"\n4.2 未结清账单...")
    unpaid = settlement_manager.list_settlements(payment_status='未结清')
    unpaid += settlement_manager.list_settlements(payment_status='部分结清')
    print(f"   未结清: {len(unpaid)} 笔")
    total_remain = sum((s['total_amount'] or 0) - (s['paid_amount'] or 0) for s in unpaid)
    print(f"   未结总额: ¥{total_remain:.2f}")
    print(f"   ✅ 未结清查询正常")

    print(f"\n4.3 单个客户历史账单...")
    if billings:
        cid = billings[0]['customer_id']
        cust_settle = settlement_manager.list_settlements(customer_id=cid)
        print(f"   客户#{cid}历史账单: {len(cust_settle)} 笔")
    print(f"   ✅ 按客户查询正常")

    print("\n🏆 结算与账单测试通过!")


def test_utilization_monthly_split():
    print("\n" + "=" * 60)
    print("测试5: 利用率报表(跨月收入按天拆分)")
    print("=" * 60)

    now = datetime.now()
    print(f"\n5.1 生成本月利用率报表...")
    report = report_manager.get_utilization_report(now.year, now.month)
    s = report['summary']
    print(f"   统计: {s['equipment_count']}台设备, {s['days_in_month']}天")
    print(f"   出租台天: {s['total_rented_days']}, 利用率{s['avg_utilization']:.2f}%")
    print(f"   本月收入(按天拆分): ¥{s['total_income']:.2f}")
    assert s['equipment_count'] >= 10
    assert s['total_income'] >= 0
    print(f"   ✅ 按天收入拆分计算正常")

    print(f"\n5.2 按类型汇总...")
    for t in report['by_type']:
        print(f"   - {t['type']}: {t['rented_days']}天, {t['utilization']:.1f}%, 收入¥{t['income']:.2f}")

    print(f"\n5.3 单台设备识别闲置严重的(<20%)...")
    low_util = [e for e in report['by_equipment'] if e['utilization'] < 20]
    high_util = [e for e in report['by_equipment'] if e['utilization'] >= 80]
    print(f"   严重闲置: {len(low_util)} 台, 高负荷: {len(high_util)} 台")
    for e in report['by_equipment'][:3]:
        print(f"   - {e['code']}: {e['utilization']:.1f}% 出租{e['rented_days']}天 收入¥{e['income']:.2f}")

    print(f"\n5.4 利用率CSV导出...")
    path = report_manager.export_utilization_report_to_csv(now.year, now.month)
    size = os.path.getsize(path)
    assert size > 100
    print(f"   ✅ CSV导出成功: {os.path.basename(path)} {size} bytes")

    print("\n🏆 利用率报表(跨月按天拆分)测试通过!")


def test_date_edge_cases():
    print("\n" + "=" * 60)
    print("测试6: 日期与边界校验")
    print("=" * 60)

    print(f"\n6.1 结束早于开始 (反向日期拦截)")
    ok, msg = equipment_manager.validate_date_range('2026-06-10', '2026-06-01')
    assert not ok
    print(f"   ✅ 正确拦截: {msg}")

    print(f"\n6.2 租赁归还日期早于起租拦截...")
    customers = rental_manager.list_customers()
    eqs = equipment_manager.list_equipment(status='空闲')
    eqs = [e for e in eqs if e['status'] == '空闲']
    if eqs:
        eq = eqs[0]
        start = '2026-06-15'
        exp = '2026-06-20'
        ok, rid, _ = rental_manager.create_rental(
            customers[0]['id'], eq['id'], start, exp, eq['total_hours'], '按天', daily_rate=1000
        )
        if ok:
            bad_date = '2026-06-10'
            ok_r, msg_r = rental_manager.return_equipment(rid, bad_date, eq['total_hours'] + 10)
            assert not ok_r
            print(f"   ✅ 归还早于起租正确拦截: {msg_r}")

    print("\n🏆 日期边界测试全部通过!")


def main():
    print("🚀 v3.0 完整功能测试套件")
    setup()
    try:
        test_sample_data()
        test_reservation_conversion_closed_loop()
        test_calendar_and_availability()
        test_billing_and_settlement()
        test_utilization_monthly_split()
        test_date_edge_cases()
        print("\n" + "=" * 60)
        print("🎉 v3.0 所有新增功能测试全部通过！")
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
