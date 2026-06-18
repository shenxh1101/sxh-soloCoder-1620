from datetime import datetime, timedelta
import equipment_manager
import rental_manager
from database import init_db


def seed_sample_data():
    init_db()
    print("开始初始化示例数据...\n")

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
                'return_offset': 7,
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
                print(f"    设备已归还，总费用: ¥{result['total_amount']:.2f}")
            else:
                print(f"    归还失败: {result}")

    print()

    maintenance_records = [
        ('WJ-001', (today - timedelta(days=60)).strftime('%Y-%m-%d'), 800, '常规保养', 800),
        ('WJ-003', (today - timedelta(days=30)).strftime('%Y-%m-%d'), 180, '常规保养', 600),
        ('QZ-002', (today - timedelta(days=90)).strftime('%Y-%m-%d'), 1000, '常规保养', 1200),
        ('ZZ-002', (today - timedelta(days=45)).strftime('%Y-%m-%d'), 300, '常规保养', 500),
    ]

    for code, m_date, hours, m_type, cost in maintenance_records:
        eq = eq_map[code]
        ok, msg = equipment_manager.add_maintenance_record(eq['id'], m_date, hours, m_type, cost)
        print(f"  {code}: {msg}")

    print("\n示例数据初始化完成！")


if __name__ == '__main__':
    seed_sample_data()
