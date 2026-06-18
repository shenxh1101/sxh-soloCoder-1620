import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import equipment_manager
import rental_manager
import report_manager


def test_equipment_manager():
    print("\n" + "=" * 60)
    print("测试: 设备管理模块")
    print("=" * 60)

    print("\n1. 测试列出所有设备...")
    equipments = equipment_manager.list_equipment()
    assert len(equipments) >= 10, f"设备数量不足: {len(equipments)}"
    print(f"   ✅ 找到 {len(equipments)} 台设备")

    print("\n2. 测试按类型筛选设备...")
    excavators = equipment_manager.list_equipment(eq_type='挖掘机')
    assert len(excavators) == 3, f"挖掘机数量应为3，实际{len(excavators)}"
    print(f"   ✅ 找到 {len(excavators)} 台挖掘机")

    print("\n3. 测试按状态筛选设备...")
    rented = equipment_manager.list_equipment(status='在租')
    idle = equipment_manager.list_equipment(status='空闲')
    print(f"   ✅ 在租 {len(rented)} 台，空闲 {len(idle)} 台")

    print("\n4. 测试获取单个设备...")
    eq = equipment_manager.get_equipment_by_code('WJ-001')
    assert eq is not None, "未找到设备 WJ-001"
    assert eq['type'] == '挖掘机', f"类型错误: {eq['type']}"
    print(f"   ✅ 找到设备: {eq['code']} - {eq['type']} {eq['model']}")

    print("\n5. 测试保养提醒...")
    alerts = equipment_manager.get_maintenance_alert_list()
    print(f"   ✅ 保养提醒数量: {len(alerts)}")
    for a in alerts[:3]:
        print(f"      - {a['code']}: 距下次保养 {a['hours_until_next']:.1f}h")

    print("\n6. 测试添加保养记录...")
    eq = equipment_manager.get_equipment_by_code('WJ-002')
    ok, msg = equipment_manager.add_maintenance_record(
        eq['id'], datetime.now().strftime('%Y-%m-%d'), 160, '测试保养', 500, '测试备注'
    )
    assert ok, f"保养记录添加失败: {msg}"
    records = equipment_manager.list_maintenance(eq['id'])
    assert len(records) >= 1, "保养记录未保存"
    print(f"   ✅ 保养记录添加成功，共 {len(records)} 条记录")

    print("\n🏆 设备管理模块测试通过!")


def test_rental_manager():
    print("\n" + "=" * 60)
    print("测试: 租赁管理模块")
    print("=" * 60)

    print("\n1. 测试客户管理...")
    customers = rental_manager.list_customers()
    assert len(customers) >= 5, f"客户数量不足: {len(customers)}"
    print(f"   ✅ 找到 {len(customers)} 个客户")

    print("\n2. 测试客户搜索...")
    results = rental_manager.search_customers('宏达')
    assert len(results) >= 1, "搜索失败"
    print(f"   ✅ 搜索到 {len(results)} 个客户")

    print("\n3. 测试列出租赁记录...")
    all_rentals = rental_manager.list_rentals()
    active_rentals = rental_manager.list_rentals(status='在租')
    returned_rentals = rental_manager.list_rentals(status='已归还')
    assert len(all_rentals) >= 6, f"租赁记录不足: {len(all_rentals)}"
    print(f"   ✅ 总记录: {len(all_rentals)}, 在租: {len(active_rentals)}, 已归还: {len(returned_rentals)}")

    print("\n4. 测试租赁详情...")
    rental = rental_manager.get_rental_by_id(3)
    assert rental is not None, "未找到租赁记录"
    assert rental['status'] == '已归还', f"状态错误: {rental['status']}"
    print(f"   ✅ 租赁ID: {rental['id']}, 客户: {rental['customer_name']}, 金额: ¥{rental['total_amount']:.2f}")

    print("\n5. 测试费用计算（按小时）...")
    fees = rental_manager.calculate_rental_fee(3, rental['actual_return_date'], rental['return_hours'])
    assert fees is not None, "费用计算失败"
    assert fees['total_amount'] > 0, "总金额应为正数"
    print(f"   ✅ 基本租金: ¥{fees['base_rent']:.2f}, 超期罚款: ¥{fees['overtime_fine']:.2f}, 总计: ¥{fees['total_amount']:.2f}")

    print("\n6. 测试创建新租赁和归还流程...")
    idle_eq = equipment_manager.list_equipment(status='空闲')[0]
    customer = customers[0]
    start_date = datetime.now().strftime('%Y-%m-%d')
    expected_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')

    ok, rid, msg = rental_manager.create_rental(
        customer['id'], idle_eq['id'], start_date, expected_date,
        idle_eq['total_hours'], '按天', daily_rate=2000
    )
    assert ok, f"创建租赁失败: {msg}"
    print(f"   ✅ 新租赁创建成功，ID: {rid}")

    eq_after = equipment_manager.get_equipment_by_id(idle_eq['id'])
    assert eq_after['status'] == '在租', "设备状态未更新"
    print(f"   ✅ 设备状态已更新为: {eq_after['status']}")

    return_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    return_hours = idle_eq['total_hours'] + 40
    ok, result = rental_manager.return_equipment(rid, return_date, return_hours)
    assert ok, f"归还失败: {result}"
    print(f"   ✅ 设备归还成功，总费用: ¥{result['total_amount']:.2f}")

    eq_final = equipment_manager.get_equipment_by_id(idle_eq['id'])
    assert eq_final['status'] == '空闲', "设备归还后状态未更新"
    assert eq_final['total_hours'] == return_hours, "工时未更新"
    print(f"   ✅ 设备状态已更新为: {eq_final['status']}, 工时: {eq_final['total_hours']:.1f}h")

    print("\n🏆 租赁管理模块测试通过!")


def test_report_manager():
    print("\n" + "=" * 60)
    print("测试: 报表统计模块")
    print("=" * 60)

    print("\n1. 测试设备类型状态统计...")
    stats = report_manager.get_equipment_status_by_type()
    assert len(stats) == 5, f"设备类型数量错误: {len(stats)}"
    print(f"   ✅ 统计了 {len(stats)} 种设备类型")
    for eq_type, s in stats.items():
        print(f"      - {eq_type}: 总数{s['总数']}, 在租{s['在租']}, 空闲{s['空闲']}")

    print("\n2. 测试每日状态报表...")
    report = report_manager.get_daily_status_report()
    assert 'equipments' in report, "报表数据不完整"
    assert 'type_stats' in report, "报表数据不完整"
    print(f"   ✅ 报表日期: {report['report_date']}")
    print(f"   ✅ 设备明细条数: {len(report['equipments'])}")

    print("\n3. 测试月度收入报表...")
    now = datetime.now()
    report = report_manager.get_monthly_income_report(now.year, now.month)
    print(f"   ✅ 报表期间: {report['year']}年{report['month']}月")
    print(f"   ✅ 租赁总数: {report['summary']['租赁总数']} 笔")
    print(f"   ✅ 总收入: ¥{report['summary']['总收入合计']:.2f}")
    print(f"   ✅ 按客户汇总: {len(report['by_customer'])} 个客户")
    print(f"   ✅ 按类型汇总: {len(report['by_type'])} 种设备")
    for item in report['by_customer'][:3]:
        print(f"      - {item['客户']}: ¥{item['总收入']:.2f} ({item['租赁次数']}笔)")

    print("\n4. 测试CSV导出...")
    daily_path = report_manager.export_daily_report_to_csv()
    assert os.path.exists(daily_path), "每日报表导出失败"
    print(f"   ✅ 每日报表已导出: {os.path.basename(daily_path)} ({os.path.getsize(daily_path)} bytes)")

    monthly_path = report_manager.export_monthly_report_to_csv(now.year, now.month)
    assert os.path.exists(monthly_path), "月度报表导出失败"
    print(f"   ✅ 月度报表已导出: {os.path.basename(monthly_path)} ({os.path.getsize(monthly_path)} bytes)")

    print("\n🏆 报表统计模块测试通过!")


def main():
    print("🚀 开始运行完整测试套件...")
    try:
        test_equipment_manager()
        test_rental_manager()
        test_report_manager()
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！系统运行正常！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
