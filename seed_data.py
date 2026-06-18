from datetime import datetime, timedelta
import equipment_manager
import rental_manager
import reservation_manager
import settlement_manager
from database import init_db


def seed_sample_data():
    init_db()
    print("开始初始化示例数据 v3.0...\n")

    equipments = [
        ('WJ-001', '挖掘机', '卡特彼勒320D', 280.0, 200),
        ('WJ-002', '挖掘机', '小松PC200', 260.0, 200),
        ('WJ-003', '挖掘机', '神钢SK210', 270.0, 200),
        ('ZZ-001', '装载机', '柳工CLG856', 220.0, 200),
        ('ZZ-002', '装载机', '徐工LW500FN', 210.0, 200),
        ('QZ-001', '起重机', '中联重科QY25V', 450.0, 250),
        ('QZ-002', '起重机', '三一STC250', 480.0, 250),
        ('YL-001', '压路机', '徐工XS223J', 180.0, 200),
        ('YL-002', '压路机', '三一SSR220AC', 190.0, 200),
        ('TT-001', '推土机', '山推SD16', 240.0, 200),
        ('TT-002', '推土机', '小松D65PX', 260.0, 200),
    ]

    for code, eq_type, model, rate, interval in equipments:
        ok, msg = equipment_manager.add_equipment(code, eq_type, model, rate, interval)
        print(f"  {msg}")

    print()

    customers = [
        ('宏达建设工程有限公司', '张经理', '13800138001'),
        ('恒达路桥有限公司', '李总', '13900139002'),
        ('鑫源房地产开发有限公司', '王主任', '13700137003'),
        ('永兴市政工程有限公司', '赵工', '13600136004'),
        ('博远建筑劳务有限公司', '孙队长', '13500135005'),
    ]

    customer_ids = []
    for name, contact, phone in customers:
        ok, cid, msg = rental_manager.add_customer(name, contact, phone)
        print(f"  {msg}")
        customer_ids.append(cid)

    print()

    today = datetime.now().date()

    eq_list = equipment_manager.list_equipment()
    eq_map = {e['code']: e for e in eq_list}

    rentals = [
        {
            'customer_idx': 0,
            'code': 'WJ-001',
            'start_offset': 5,
            'expected_days': 10,
            'start_hours': 850,
            'rental_mode': '按天',
            'daily_rate': 2240,
            'actual': None,
        },
        {
            'customer_idx': 1,
            'code': 'QZ-001',
            'start_offset': 3,
            'expected_days': 5,
            'start_hours': 1200,
            'rental_mode': '按天',
            'daily_rate': 3600,
            'actual': None,
        },
        {
            'customer_idx': 2,
            'code': 'ZZ-001',
            'start_offset': 7,
            'expected_days': 3,
            'start_hours': 500,
            'rental_mode': '按小时',
            'hourly_rate': 220,
            'actual': {
                'return_offset': 5,
                'return_hours': 524,
            },
        },
        {
            'customer_idx': 3,
            'code': 'YL-001',
            'start_offset': 15,
            'expected_days': 4,
            'start_hours': 380,
            'rental_mode': '按天',
            'daily_rate': 1440,
            'actual': {
                'return_offset': 10,
                'return_hours': 416,
            },
        },
        {
            'customer_idx': 4,
            'code': 'TT-001',
            'start_offset': 20,
            'expected_days': 7,
            'start_hours': 720,
            'rental_mode': '按天',
            'daily_rate': 1920,
            'actual': {
                'return_offset': 12,
                'return_hours': 785,
            },
        },
        {
            'customer_idx': 0,
            'code': 'WJ-002',
            'start_offset': 30,
            'expected_days': 15,
            'start_hours': 150,
            'rental_mode': '按天',
            'daily_rate': 2080,
            'actual': {
                'return_offset': 18,
                'return_hours': 290,
            },
        },
    ]

    created_rentals = []
    for r in rentals:
        eq = eq_map[r['code']]
        start_date = (today - timedelta(days=r['start_offset'])).strftime('%Y-%m-%d')
        expected_return_date = (today - timedelta(days=r['start_offset']) + timedelta(days=r['expected_days'])).strftime('%Y-%m-%d')

        if r['rental_mode'] == '按天':
            ok, rid, msg = rental_manager.create_rental(
                customer_ids[r['customer_idx']], eq['id'],
                start_date, expected_return_date,
                r['start_hours'], '按天', daily_rate=r['daily_rate']
            )
        else:
            ok, rid, msg = rental_manager.create_rental(
                customer_ids[r['customer_idx']], eq['id'],
                start_date, expected_return_date,
                r['start_hours'], '按小时', hourly_rate=r['hourly_rate']
            )
        print(f"  {msg}")

        if r['actual']:
            actual_return_date = (today - timedelta(days=r['actual']['return_offset'])).strftime('%Y-%m-%d')
            ok, result = rental_manager.return_equipment(rid, actual_return_date, r['actual']['return_hours'])
            if ok:
                sid = result.get('settlement_id')
                setl_info = f" (结算单#{sid})" if sid else ""
                print(f"    ✅ 设备已归还，总费用: ¥{result['total_amount']:.2f}{setl_info}")
                if sid and r['customer_idx'] in (0, 3):
                    ok_p, msg_p = settlement_manager.record_payment(sid, result['total_amount'], '示例数据：全额结清')
                    if ok_p:
                        print(f"    ✅ {msg_p}")
            else:
                print(f"    ❌ 归还失败: {result}")
        created_rentals.append((rid, r))

    print()

    print("  --- 示例预约数据 ---")
    reservations = [
        {
            'customer_idx': 0,
            'code': 'ZZ-002',
            'start_offset': -3,
            'duration_days': 4,
            'mode': '按天',
            'daily': 1680,
            'confirmed': True,
        },
        {
            'customer_idx': 2,
            'code': 'YL-002',
            'start_offset': -7,
            'duration_days': 5,
            'mode': '按天',
            'daily': 1520,
            'confirmed': False,
        },
        {
            'customer_idx': 4,
            'code': 'TT-002',
            'start_offset': -10,
            'duration_days': 6,
            'mode': '按天',
            'daily': 2080,
            'confirmed': True,
        },
    ]
    created_reservations = []
    for rv in reservations:
        eq = eq_map[rv['code']]
        start_d = (today + timedelta(days=rv['start_offset'])).strftime('%Y-%m-%d')
        end_d = (today + timedelta(days=rv['start_offset']) + timedelta(days=rv['duration_days'])).strftime('%Y-%m-%d')
        ok, rvid, msg = reservation_manager.create_reservation(
            customer_ids[rv['customer_idx']], eq['id'],
            start_d, end_d, rv['mode'],
            expected_daily_rate=rv.get('daily'),
            expected_hourly_rate=rv.get('hourly'),
            remarks='示例预约数据'
        )
        if ok:
            if rv['confirmed']:
                reservation_manager.confirm_reservation(rvid)
            print(f"  ✅ 预约#{rvid} {eq['code']} {start_d}~{end_d} {'[已确认]' if rv['confirmed'] else '[待确认]'}")
            created_reservations.append((rvid, rv))
        else:
            print(f"  ❌ 预约失败: {msg[:60]}")

    if created_reservations:
        rvid, rv = created_reservations[0]
        eq = eq_map[rv['code']]
        ok_conv, rental_id, msg_conv = reservation_manager.convert_reservation_to_rental(
            rvid, eq['total_hours'] + 5, '从示例预约转换而来'
        )
        if ok_conv:
            print(f"\n  ✅ 预约#{rvid} 闭环转租赁成功: {msg_conv}")
            ret_date = (today + timedelta(days=rv['start_offset'] + rv['duration_days'] - 1)).strftime('%Y-%m-%d')
            ok_ret, result_ret = rental_manager.return_equipment(
                rental_id, ret_date, eq['total_hours'] + 5 + rv['duration_days'] * 7
            )
            if ok_ret:
                sid = result_ret.get('settlement_id')
                print(f"  ✅ 模拟归还并结算完成，总费用 ¥{result_ret['total_amount']:.2f} 结算单#{sid}")
        else:
            print(f"\n  ⚠️  预约转租赁: {msg_conv}")

    print()

    maintenance_records = [
        ('WJ-001', (today - timedelta(days=60)).strftime('%Y-%m-%d'), 800, '常规保养', 800),
        ('WJ-003', (today - timedelta(days=30)).strftime('%Y-%m-%d'), 180, '常规保养', 600),
        ('QZ-002', (today - timedelta(days=90)).strftime('%Y-%m-%d'), 1000, '常规保养', 1200),
        ('ZZ-002', (today - timedelta(days=45)).strftime('%Y-%m-%d'), 300, '常规保养', 500),
    ]

    for code, m_date, hours, m_type, cost in maintenance_records:
        eq = eq_map[code]
        ok, info, msg = equipment_manager.add_maintenance_record(eq['id'], m_date, hours, m_type, cost)
        extra = f"，状态 {info['prev_status']}→{info['new_status']}" if ok and info else ""
        print(f"  {code}: {msg}{extra}")

    equipment_manager.refresh_all_maintenance_statuses()

    print()
    print("=" * 60)
    print("  ✅ 示例数据加载完成！")
    print(f"    - 设备: {len(equipments)} 台")
    print(f"    - 客户: {len(customers)} 家")
    print(f"    - 租赁: {len(created_rentals)} 笔")
    print(f"    - 预约: {len(reservations)} 条（含1条闭环转租赁示例）")
    print(f"    - 保养: {len(maintenance_records)} 条")
    print(f"    - 结算单: 已为已归还租赁自动生成")
    print("=" * 60)


if __name__ == '__main__':
    seed_sample_data()
