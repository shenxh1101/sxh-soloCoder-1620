import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
import equipment_manager
import rental_manager
import report_manager
import seed_data


def print_header(title):
    width = 70
    print()
    print("=" * width)
    print(title.center(width))
    print("=" * width)


def print_menu(options):
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. 返回上级菜单")


def input_int(prompt, min_val=None, max_val=None):
    while True:
        try:
            val = int(input(prompt))
            if min_val is not None and val < min_val:
                print(f"输入不能小于 {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"输入不能大于 {max_val}")
                continue
            return val
        except ValueError:
            print("请输入有效数字")


def input_float(prompt, min_val=None):
    while True:
        try:
            val = float(input(prompt))
            if min_val is not None and val < min_val:
                print(f"输入不能小于 {min_val}")
                continue
            return val
        except ValueError:
            print("请输入有效数字")


def input_date(prompt, allow_empty=False):
    while True:
        s = input(prompt).strip()
        if not s and allow_empty:
            return None
        try:
            datetime.strptime(s, '%Y-%m-%d')
            return s
        except ValueError:
            print("日期格式错误，请使用 YYYY-MM-DD 格式")


def show_maintenance_alerts():
    alerts = equipment_manager.get_maintenance_alert_list()
    if alerts:
        print_header("⚠️  保养提醒清单")
        print(f"{'设备编号':<10}{'设备类型':<8}{'型号':<12}{'累计工时':>10}{'距上次保养':>12}{'距下次保养':>12}")
        print("-" * 70)
        for a in alerts:
            status = "🔴 需立即保养" if a['hours_until_next'] <= 0 else "🟡 即将保养"
            print(f"{a['code']:<10}{a['type']:<8}{a['model']:<12}{a['total_hours']:>8.1f}h{a['hours_since_maintenance']:>10.1f}h{a['hours_until_next']:>10.1f}h  {status}")
        print()


def equipment_menu():
    while True:
        print_header("设备管理")
        print_menu([
            "添加新设备",
            "查看所有设备",
            "按类型查看设备",
            "查看保养提醒",
            "记录设备保养",
            "查看保养记录",
        ])
        choice = input_int("请选择操作: ", 0, 6)

        if choice == 0:
            break
        elif choice == 1:
            print("\n--- 添加新设备 ---")
            print("设备类型可选:", ', '.join(equipment_manager.EQUIPMENT_TYPES))
            code = input("设备编号: ").strip()
            eq_type = input("设备类型: ").strip()
            model = input("型号: ").strip()
            hourly_rate = input_float("小时费率 (元/小时): ", 0)
            interval = input_int("保养周期(小时, 默认200): ", 1) or 200
            ok, msg = equipment_manager.add_equipment(code, eq_type, model, hourly_rate, interval)
            print(msg)

        elif choice == 2:
            print("\n--- 所有设备 ---")
            equipments = equipment_manager.list_equipment()
            print_equipment_table(equipments)

        elif choice == 3:
            print("\n--- 按类型查看设备 ---")
            print("设备类型:", ', '.join(equipment_manager.EQUIPMENT_TYPES))
            eq_type = input("输入设备类型(留空查看全部): ").strip() or None
            status = input("输入状态(在租/空闲, 留空查看全部): ").strip() or None
            equipments = equipment_manager.list_equipment(eq_type, status)
            print_equipment_table(equipments)

        elif choice == 4:
            show_maintenance_alerts()

        elif choice == 5:
            print("\n--- 记录设备保养 ---")
            code = input("设备编号: ").strip()
            eq = equipment_manager.get_equipment_by_code(code)
            if not eq:
                print("设备不存在")
                continue
            print(f"设备: {eq['code']} - {eq['type']} {eq['model']}")
            print(f"当前累计工时: {eq['total_hours']:.1f}h")
            m_date = input_date("保养日期 (YYYY-MM-DD, 默认今天): ", True) or datetime.now().strftime('%Y-%m-%d')
            hours = input_float(f"保养时工时 (默认{int(eq['total_hours'])}): ", 0) or eq['total_hours']
            m_type = input("保养类型 (默认常规保养): ").strip() or "常规保养"
            cost = input_float("保养费用 (默认0): ", 0) or 0
            remarks = input("备注 (可选): ").strip()
            ok, msg = equipment_manager.add_maintenance_record(eq['id'], m_date, hours, m_type, cost, remarks)
            print(msg)

        elif choice == 6:
            print("\n--- 保养记录 ---")
            code = input("设备编号 (留空查看全部): ").strip()
            eq_id = None
            if code:
                eq = equipment_manager.get_equipment_by_code(code)
                if eq:
                    eq_id = eq['id']
                else:
                    print("设备不存在，将显示全部记录")
            records = equipment_manager.list_maintenance(eq_id)
            if records:
                print(f"{'日期':<12}{'设备编号':<10}{'设备类型':<8}{'保养工时':>10}{'类型':<10}{'费用':>10}{'备注'}")
                print("-" * 80)
                for r in records:
                    print(f"{r['maintenance_date']:<12}{r['equipment_code']:<10}{r['equipment_type']:<8}{r['hours_at_maintenance']:>8.1f}h{r['type']:<10}{r['cost']:>8.0f}元{r['remarks'] or ''}")
            else:
                print("暂无保养记录")


def print_equipment_table(equipments):
    if not equipments:
        print("暂无设备")
        return
    print(f"{'编号':<10}{'类型':<8}{'型号':<14}{'小时费率':>10}{'累计工时':>10}{'状态':<8}{'距下次保养':>12}")
    print("-" * 75)
    for e in equipments:
        hours_until = (e['maintenance_interval'] - (e['total_hours'] - e['last_maintenance_hours']))
        print(f"{e['code']:<10}{e['type']:<8}{e['model']:<14}{e['hourly_rate']:>8.0f}元/h{e['total_hours']:>8.1f}h{e['status']:<8}{max(0, hours_until):>10.1f}h")


def customer_menu():
    while True:
        print_header("客户管理")
        print_menu([
            "添加新客户",
            "查看所有客户",
            "搜索客户",
        ])
        choice = input_int("请选择操作: ", 0, 3)

        if choice == 0:
            break
        elif choice == 1:
            print("\n--- 添加新客户 ---")
            name = input("客户名称: ").strip()
            contact = input("联系人: ").strip()
            phone = input("联系电话: ").strip()
            ok, cid, msg = rental_manager.add_customer(name, contact, phone)
            print(msg)

        elif choice == 2:
            print("\n--- 所有客户 ---")
            customers = rental_manager.list_customers()
            if customers:
                print(f"{'ID':<6}{'客户名称':<30}{'联系人':<12}{'联系电话':<15}")
                print("-" * 70)
                for c in customers:
                    print(f"{c['id']:<6}{c['name']:<30}{c['contact']:<12}{c['phone']:<15}")
            else:
                print("暂无客户")

        elif choice == 3:
            keyword = input("搜索关键字: ").strip()
            customers = rental_manager.search_customers(keyword)
            if customers:
                print(f"{'ID':<6}{'客户名称':<30}{'联系人':<12}{'联系电话':<15}")
                print("-" * 70)
                for c in customers:
                    print(f"{c['id']:<6}{c['name']:<30}{c['contact']:<12}{c['phone']:<15}")
            else:
                print("未找到匹配的客户")


def rental_menu():
    while True:
        print_header("租赁管理")
        print_menu([
            "创建新租赁",
            "查看在租设备",
            "查看所有租赁记录",
            "设备归还",
            "查看租赁详情",
        ])
        choice = input_int("请选择操作: ", 0, 5)

        if choice == 0:
            break
        elif choice == 1:
            create_new_rental()
        elif choice == 2:
            rentals = rental_manager.list_rentals(status='在租')
            print_rental_table(rentals, "在租设备")
        elif choice == 3:
            print("\n--- 租赁记录筛选 ---")
            status = input("状态(在租/已归还, 留空全部): ").strip() or None
            rentals = rental_manager.list_rentals(status=status)
            print_rental_table(rentals, "租赁记录")
        elif choice == 4:
            process_return()
        elif choice == 5:
            rid = input_int("租赁ID: ", 1)
            r = rental_manager.get_rental_by_id(rid)
            if r:
                print_rental_detail(r)
            else:
                print("租赁记录不存在")


def create_new_rental():
    print("\n--- 创建新租赁 ---")
    print("空闲设备列表:")
    idle_equipments = equipment_manager.list_equipment(status='空闲')
    print_equipment_table(idle_equipments)

    code = input("\n设备编号: ").strip()
    eq = equipment_manager.get_equipment_by_code(code)
    if not eq:
        print("设备不存在")
        return
    if eq['status'] == '在租':
        print("该设备正在租赁中")
        return

    customers = rental_manager.list_customers()
    print("\n客户列表:")
    print(f"{'ID':<6}{'客户名称':<30}{'联系人':<12}")
    print("-" * 50)
    for c in customers:
        print(f"{c['id']:<6}{c['name']:<30}{c['contact']:<12}")

    customer_id = input_int("客户ID: ", 1)
    customer = rental_manager.get_customer_by_id(customer_id)
    if not customer:
        print("客户不存在")
        return

    start_date = input_date("起租日期 (YYYY-MM-DD, 默认今天): ", True) or datetime.now().strftime('%Y-%m-%d')
    expected_return_date = input_date("预计归还日期 (YYYY-MM-DD): ")
    start_hours = input_float(f"起租时工时 (默认{int(eq['total_hours'])}): ", 0) or eq['total_hours']

    print("\n租赁模式:")
    print("  1. 按天 (每日8小时)")
    print("  2. 按小时")
    mode_choice = input_int("请选择: ", 1, 2)
    rental_mode = '按天' if mode_choice == 1 else '按小时'

    if rental_mode == '按天':
        default_daily = eq['hourly_rate'] * 8
        daily_rate = input_float(f"每日租金 (默认{default_daily:.0f}元/天): ", 0) or default_daily
        hourly_rate = None
    else:
        hourly_rate = input_float(f"小时费率 (默认{eq['hourly_rate']:.0f}元/小时): ", 0) or eq['hourly_rate']
        daily_rate = None

    remarks = input("备注 (可选): ").strip()

    ok, rid, msg = rental_manager.create_rental(
        customer_id, eq['id'], start_date, expected_return_date,
        start_hours, rental_mode, daily_rate, hourly_rate, remarks
    )
    print(msg)


def process_return():
    print("\n--- 设备归还 ---")
    rentals = rental_manager.list_rentals(status='在租')
    print_rental_table(rentals, "在租设备")

    if not rentals:
        return

    rid = input_int("\n选择归还的租赁ID: ", 1)
    r = rental_manager.get_rental_by_id(rid)
    if not r or r['status'] != '在租':
        print("无效的租赁ID")
        return

    print(f"\n设备: {r['equipment_code']} - {r['equipment_type']} {r['equipment_model']}")
    print(f"客户: {r['customer_name']}")
    print(f"起租工时: {r['start_hours']:.1f}h")

    actual_return_date = input_date("实际归还日期 (YYYY-MM-DD, 默认今天): ", True) or datetime.now().strftime('%Y-%m-%d')
    return_hours = input_float("归还时工时: ", r['start_hours'])

    confirm = input(f"确认归还? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    ok, result = rental_manager.return_equipment(rid, actual_return_date, return_hours)
    if ok:
        print("\n✅ 归还成功！费用明细:")
        print(f"  使用工时: {result['used_hours']:.1f} 小时")
        print(f"  租赁天数: {result['rental_days']} 天")
        print(f"  基本租金: ¥{result['base_rent']:.2f}")
        print(f"  超期罚款: ¥{result['overtime_fine']:.2f}")
        print(f"  总金额:   ¥{result['total_amount']:.2f}")
    else:
        print(f"归还失败: {result}")


def print_rental_table(rentals, title):
    print(f"\n--- {title} ---")
    if not rentals:
        print("暂无记录")
        return
    print(f"{'ID':<6}{'设备编号':<10}{'类型':<8}{'客户':<16}{'起租日期':<12}{'预计归还':<12}{'模式':<6}{'状态':<8}")
    print("-" * 85)
    for r in rentals:
        print(f"{r['id']:<6}{r['equipment_code']:<10}{r['equipment_type']:<8}{r['customer_name']:<16}{r['start_date']:<12}{r['expected_return_date']:<12}{r['rental_mode']:<6}{r['status']:<8}")


def print_rental_detail(r):
    print("\n--- 租赁详情 ---")
    print(f"租赁ID: {r['id']}")
    print(f"设备: {r['equipment_code']} - {r['equipment_type']} {r['equipment_model']}")
    print(f"客户: {r['customer_name']} (联系人: {r['customer_contact']}, 电话: {r['customer_phone']})")
    print(f"起租日期: {r['start_date']}")
    print(f"预计归还: {r['expected_return_date']}")
    if r['actual_return_date']:
        print(f"实际归还: {r['actual_return_date']}")
    print(f"起租工时: {r['start_hours']:.1f}h")
    if r['return_hours']:
        print(f"归还工时: {r['return_hours']:.1f}h")
        print(f"使用工时: {r['return_hours'] - r['start_hours']:.1f}h")
    print(f"租赁模式: {r['rental_mode']}")
    if r['rental_mode'] == '按天':
        print(f"日租金: ¥{r['daily_rate']:.2f}/天")
    else:
        print(f"小时费率: ¥{r['hourly_rate']:.2f}/小时")
    print(f"状态: {r['status']}")
    if r['status'] == '已归还':
        print(f"基本租金: ¥{r['base_rent']:.2f}")
        print(f"超期罚款: ¥{r['overtime_fine']:.2f}")
        print(f"总金额: ¥{r['total_amount']:.2f}")
    if r['remarks']:
        print(f"备注: {r['remarks']}")


def report_menu():
    while True:
        print_header("报表统计")
        print_menu([
            "设备状态统计(按类型)",
            "每日设备状态报表",
            "月度租赁收入报表(按客户汇总)",
            "导出每日状态报表(CSV)",
            "导出月度收入报表(CSV)",
        ])
        choice = input_int("请选择操作: ", 0, 5)

        if choice == 0:
            break
        elif choice == 1:
            stats = report_manager.get_equipment_status_by_type()
            print(f"\n{'设备类型':<10}{'总数':>6}{'在租':>6}{'空闲':>6}")
            print("-" * 35)
            total = {'总数': 0, '在租': 0, '空闲': 0}
            for eq_type, s in stats.items():
                print(f"{eq_type:<10}{s['总数']:>6}{s['在租']:>6}{s['空闲']:>6}")
                total['总数'] += s['总数']
                total['在租'] += s['在租']
                total['空闲'] += s['空闲']
            print("-" * 35)
            print(f"{'合计':<10}{total['总数']:>6}{total['在租']:>6}{total['空闲']:>6}")

        elif choice == 2:
            report_date = input_date("报表日期 (YYYY-MM-DD, 默认今天): ", True)
            report = report_manager.get_daily_status_report(report_date)
            print(f"\n📅 每日设备状态报表 - {report['report_date']}")
            print(f"\n{'设备类型':<10}{'总数':>6}{'在租':>6}{'空闲':>6}")
            print("-" * 35)
            for eq_type, s in report['type_stats'].items():
                print(f"{eq_type:<10}{s['总数']:>6}{s['在租']:>6}{s['空闲']:>6}")
            print(f"\n设备明细:")
            print(f"{'编号':<10}{'类型':<8}{'状态':<8}{'客户':<16}{'起租':<12}{'预计归还':<12}{'累计工时':>10}{'距下次保养':>12}")
            print("-" * 95)
            for e in report['equipments']:
                hours_until = (e['maintenance_interval'] - (e['total_hours'] - e['last_maintenance_hours']))
                print(f"{e['code']:<10}{e['type']:<8}{e['status']:<8}{(e['customer_name'] or '-'):<16}{(e['start_date'] or '-'):<12}{(e['expected_return_date'] or '-'):<12}{e['total_hours']:>8.1f}h{max(0, hours_until):>10.1f}h")

        elif choice == 3:
            now = datetime.now()
            year = input_int(f"年份 (默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份 (默认{now.month}): ", 1, 12) or now.month
            report = report_manager.get_monthly_income_report(year, month)
            print(f"\n📊 月度租赁收入报表 - {year}年{month}月")
            print(f"\n汇总统计:")
            print(f"  租赁总数: {report['summary']['租赁总数']} 笔")
            print(f"  基本租金合计: ¥{report['summary']['基本租金合计']:.2f}")
            print(f"  超期罚款合计: ¥{report['summary']['超期罚款合计']:.2f}")
            print(f"  总收入合计: ¥{report['summary']['总收入合计']:.2f}")

            if report['by_customer']:
                print(f"\n按客户汇总:")
                print(f"{'客户名称':<25}{'租赁次数':>10}{'基本租金':>14}{'超期罚款':>14}{'总收入':>14}")
                print("-" * 80)
                for item in report['by_customer']:
                    print(f"{item['客户']:<25}{item['租赁次数']:>10}¥{item['基本租金']:>12.2f}¥{item['超期罚款']:>12.2f}¥{item['总收入']:>12.2f}")

            if report['by_type']:
                print(f"\n按设备类型汇总:")
                print(f"{'设备类型':<10}{'租赁次数':>10}{'总收入':>14}")
                print("-" * 40)
                for item in report['by_type']:
                    print(f"{item['设备类型']:<10}{item['租赁次数']:>10}¥{item['总收入']:>12.2f}")

        elif choice == 4:
            report_date = input_date("报表日期 (YYYY-MM-DD, 默认今天): ", True)
            filepath = report_manager.export_daily_report_to_csv(report_date)
            print(f"✅ 报表已导出: {filepath}")

        elif choice == 5:
            now = datetime.now()
            year = input_int(f"年份 (默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份 (默认{now.month}): ", 1, 12) or now.month
            filepath = report_manager.export_monthly_report_to_csv(year, month)
            print(f"✅ 报表已导出: {filepath}")


def main():
    init_db()
    db_exists = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db'))

    if not db_exists or os.path.getsize(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')) < 10000:
        print("首次运行，是否加载示例数据? (y/n): ", end='')
        if input().strip().lower() == 'y':
            seed_data.seed_sample_data()

    print_header("🏗️  工程机械租赁管理系统 v1.0")
    show_maintenance_alerts()

    while True:
        print_header("主菜单")
        print_menu([
            "设备管理",
            "客户管理",
            "租赁管理",
            "报表统计",
            "重新加载示例数据",
        ])
        choice = input_int("请选择操作: ", 0, 5)

        if choice == 0:
            print("\n👋 感谢使用，再见！")
            sys.exit(0)
        elif choice == 1:
            equipment_menu()
        elif choice == 2:
            customer_menu()
        elif choice == 3:
            rental_menu()
        elif choice == 4:
            report_menu()
        elif choice == 5:
            confirm = input("确定重新加载示例数据? 这将覆盖所有现有数据 (y/n): ").strip().lower()
            if confirm == 'y':
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')
                if os.path.exists(db_path):
                    os.remove(db_path)
                seed_data.seed_sample_data()


if __name__ == '__main__':
    main()
