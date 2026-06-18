import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
import equipment_manager
import rental_manager
import reservation_manager
import report_manager
import seed_data


def print_header(title):
    width = 80
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
            raw = input(prompt).strip()
            if raw == '' and min_val is None:
                return None
            val = int(raw)
            if min_val is not None and val < min_val:
                print(f"输入不能小于 {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"输入不能大于 {max_val}")
                continue
            return val
        except ValueError:
            print("请输入有效数字")


def input_float(prompt, min_val=None, default=None):
    while True:
        try:
            raw = input(prompt).strip()
            if raw == '':
                if default is not None:
                    return default
                if min_val is None:
                    return None
            val = float(raw)
            if min_val is not None and val < min_val:
                print(f"输入不能小于 {min_val}")
                continue
            return val
        except ValueError:
            print("请输入有效数字")


def input_date(prompt, allow_empty=False, default_today=False, not_before=None):
    while True:
        default_hint = ''
        if default_today:
            default_hint = ' (默认今天)'
        s = input(f"{prompt}{default_hint}: ").strip()
        if not s:
            if default_today:
                s = datetime.now().strftime('%Y-%m-%d')
            elif allow_empty:
                return None
            else:
                print("请输入日期")
                continue
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
        except ValueError:
            print("日期格式错误，请使用 YYYY-MM-DD 格式")
            continue
        if not_before:
            nb = datetime.strptime(not_before, '%Y-%m-%d').date()
            if dt.date() < nb:
                print(f"日期 [{s}] 不能早于 [{not_before}]，请重新输入")
                continue
        return s


def input_date_range(prompt_start, prompt_end, default_start_today=False):
    while True:
        start = input_date(prompt_start, default_today=default_start_today)
        end = input_date(prompt_end, not_before=start)
        ok, msg = equipment_manager.validate_date_range(start, end)
        if ok:
            return start, end
        print(f"日期范围错误: {msg}，请重新输入")


def show_maintenance_alerts():
    alerts = equipment_manager.get_maintenance_alert_list()
    if alerts:
        print_header("⚠️  保养提醒清单")
        print(f"{'设备编号':<10}{'设备类型':<8}{'型号':<14}{'状态':<10}{'累计工时':>10}{'距上次保养':>12}{'距下次保养':>12}")
        print("-" * 80)
        for a in alerts:
            status_tag = a['status']
            if a['hours_until_next'] <= 0:
                tag = "🔴 需立即保养"
            elif a['status'] in ('待保养', '保养中'):
                tag = f"🟠 [{a['status']}]"
            else:
                tag = "🟡 即将保养"
            print(f"{a['code']:<10}{a['type']:<8}{a['model']:<14}{status_tag:<10}"
                  f"{a['total_hours']:>8.1f}h{a['hours_since_maintenance']:>10.1f}h{a['hours_until_next']:>10.1f}h  {tag}")
        print()


def equipment_menu():
    while True:
        print_header("设备管理")
        print_menu([
            "添加新设备",
            "查看所有设备",
            "按类型/状态查看设备",
            "查看设备排期时间表",
            "保养提醒与待保养清单",
            "开始保养流程",
            "记录保养完成(含费用)",
            "查看保养记录/费用统计",
        ])
        choice = input_int("请选择操作: ", 0, 8)

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
            print("\n--- 筛选设备 ---")
            print("设备类型:", ', '.join(equipment_manager.EQUIPMENT_TYPES))
            eq_type = input("输入设备类型(留空查看全部): ").strip() or None
            print("状态可选: 空闲, 在租, 待保养, 保养中")
            status = input("输入状态(留空查看全部): ").strip() or None
            equipments = equipment_manager.list_equipment(eq_type, status)
            print_equipment_table(equipments)

        elif choice == 4:
            print("\n--- 设备排期时间表 ---")
            code = input("设备编号: ").strip()
            eq = equipment_manager.get_equipment_by_code(code)
            if not eq:
                print("设备不存在")
                continue
            days = input_int("查询未来天数(默认90): ", 1) or 90
            to_date = (datetime.now().date() + __import__('datetime').timedelta(days=days)).strftime('%Y-%m-%d')
            schedule = equipment_manager.get_equipment_schedule(eq['id'], to_date=to_date)
            print(f"\n设备 {eq['code']} - {eq['type']} {eq['model']} 未来排期:")
            if schedule:
                print(f"{'来源':<6}{'ID':<6}{'开始':<14}{'结束':<14}{'状态':<10}{'客户'}")
                print("-" * 65)
                for s in schedule:
                    print(f"{s['source']:<6}{s['id']:<6}{s['start']:<14}{s['end']:<14}{s['status']:<10}{s['customer']}")
            else:
                print("  暂无排期记录，设备空闲可用")
            upcoming = reservation_manager.get_upcoming_reservations(days=days, equipment_id=eq['id'])
            if upcoming:
                print(f"\n  未来预约: {len(upcoming)} 条")

        elif choice == 5:
            show_maintenance_alerts()

        elif choice == 6:
            print("\n--- 开始保养 ---")
            code = input("设备编号: ").strip()
            eq = equipment_manager.get_equipment_by_code(code)
            if not eq:
                print("设备不存在")
                continue
            ok, msg = equipment_manager.start_maintenance(eq['id'])
            print(msg)

        elif choice == 7:
            print("\n--- 记录保养完成 ---")
            code = input("设备编号: ").strip()
            eq = equipment_manager.get_equipment_by_code(code)
            if not eq:
                print("设备不存在")
                continue
            print(f"设备: {eq['code']} - {eq['type']} {eq['model']}")
            print(f"当前累计工时: {eq['total_hours']:.1f}h，上次保养工时: {eq['last_maintenance_hours']:.1f}h")
            m_date = input_date("保养日期", default_today=True)
            hours = input_float(f"保养时工时 (回车用当前 {int(eq['total_hours'])}): ",
                                min_val=eq['last_maintenance_hours'], default=eq['total_hours'])
            m_type = input("保养类型 (默认常规保养): ").strip() or "常规保养"
            cost = input_float("保养费用 (默认0): ", 0) or 0
            remarks = input("备注 (可选): ").strip()
            ok, info, msg = equipment_manager.add_maintenance_record(
                eq['id'], m_date, hours, m_type, cost, remarks
            )
            if ok:
                print(f"✅ {msg}")
                print(f"   距上次保养: {info['hours_since_last']:.1f}h")
                print(f"   状态变更: {info['prev_status']} → {info['new_status']}")
                if cost > 0:
                    print(f"   本次保养费用: ¥{cost:.2f}")
            else:
                print(f"❌ {msg}")

        elif choice == 8:
            maintenance_cost_menu()


def maintenance_cost_menu():
    while True:
        print_header("保养记录与费用统计")
        print_menu([
            "查看全部保养记录",
            "按月统计保养费用",
            "按设备编号查看保养记录",
        ])
        choice = input_int("请选择操作: ", 0, 3)
        if choice == 0:
            break
        elif choice == 1:
            records = equipment_manager.list_maintenance()
            print_maintenance_records(records)
        elif choice == 2:
            now = datetime.now()
            year = input_int(f"年份(默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份(默认{now.month}): ", 1, 12) or now.month
            summary = equipment_manager.get_maintenance_cost_summary(year, month)
            print(f"\n📋 {year}年{month}月保养统计")
            print(f"  保养次数: {summary['total_count']} 次")
            print(f"  总费用: ¥{summary['total_cost']:.2f}")
            if summary['by_type']:
                print("\n  按保养类型:")
                for t, data in summary['by_type'].items():
                    print(f"    - {t}: {data['次数']}次, ¥{data['费用']:.2f}")
            if summary['by_equipment']:
                print("\n  按设备:")
                for ec, data in sorted(summary['by_equipment'].items(),
                                       key=lambda x: x[1]['费用'], reverse=True):
                    print(f"    - {ec}({data['类型']}): {data['次数']}次, ¥{data['费用']:.2f}")
        elif choice == 3:
            code = input("设备编号: ").strip()
            eq = equipment_manager.get_equipment_by_code(code)
            if not eq:
                print("设备不存在")
                continue
            records = equipment_manager.list_maintenance(eq_id=eq['id'])
            print_maintenance_records(records)


def print_maintenance_records(records):
    if not records:
        print("暂无保养记录")
        return
    print(f"\n{'日期':<12}{'设备编号':<10}{'类型':<10}{'保养工时':>10}{'类别':<10}{'费用':>10}{'备注'}")
    print("-" * 80)
    total = 0
    for r in records:
        print(f"{r['maintenance_date']:<12}{r['equipment_code']:<10}{r['equipment_type']:<10}"
              f"{r['hours_at_maintenance']:>8.1f}h{r['type']:<10}{r['cost']:>8.0f}元{r['remarks'] or ''}")
        total += r['cost'] or 0
    print("-" * 80)
    print(f"{'合计':<62}¥{total:>8.2f}")


def print_equipment_table(equipments):
    if not equipments:
        print("暂无设备")
        return
    print(f"{'编号':<10}{'类型':<8}{'型号':<14}{'小时费率':>10}{'累计工时':>10}{'状态':<10}{'距下次保养':>12}")
    print("-" * 80)
    for e in equipments:
        hours_until = (e['maintenance_interval'] - (e['total_hours'] - e['last_maintenance_hours']))
        status_tag = e['status']
        if e['status'] == '待保养':
            status_tag = '🔴待保养'
        elif e['status'] == '保养中':
            status_tag = '🔧保养中'
        print(f"{e['code']:<10}{e['type']:<8}{e['model']:<14}{e['hourly_rate']:>7.0f}元/h"
              f"{e['total_hours']:>8.1f}h{status_tag:<10}{max(0, hours_until):>10.1f}h")


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
                print(f"{'ID':<6}{'客户名称':<32}{'联系人':<12}{'联系电话':<15}")
                print("-" * 70)
                for c in customers:
                    print(f"{c['id']:<6}{c['name']:<32}{c['contact']:<12}{c['phone']:<15}")
            else:
                print("暂无客户")

        elif choice == 3:
            keyword = input("搜索关键字: ").strip()
            customers = rental_manager.search_customers(keyword)
            if customers:
                print(f"{'ID':<6}{'客户名称':<32}{'联系人':<12}{'联系电话':<15}")
                print("-" * 70)
                for c in customers:
                    print(f"{c['id']:<6}{c['name']:<32}{c['contact']:<12}{c['phone']:<15}")
            else:
                print("未找到匹配的客户")


def reservation_menu():
    while True:
        print_header("预约排期管理")
        print_menu([
            "创建新预约",
            "查看即将到期预约",
            "查看所有预约",
            "确认预约",
            "取消预约",
            "预约转为正式租赁",
            "查看预约详情",
        ])
        choice = input_int("请选择操作: ", 0, 7)

        if choice == 0:
            break
        elif choice == 1:
            create_reservation_ui()
        elif choice == 2:
            days = input_int("查看未来几天(默认30): ", 1) or 30
            upcoming = reservation_manager.get_upcoming_reservations(days=days)
            print_reservation_table(upcoming, f"未来{days}天预约")
        elif choice == 3:
            status = input("状态筛选(待确认/已确认/已取消/已转租赁, 留空全部): ").strip() or None
            reservations = reservation_manager.list_reservations(status=status)
            print_reservation_table(reservations, "预约列表")
        elif choice == 4:
            rid = input_int("预约ID: ", 1)
            ok, msg = reservation_manager.confirm_reservation(rid)
            print(msg)
        elif choice == 5:
            rid = input_int("预约ID: ", 1)
            reason = input("取消原因(可选): ").strip()
            ok, msg = reservation_manager.cancel_reservation(rid, reason)
            print(msg)
        elif choice == 6:
            convert_reservation_ui()
        elif choice == 7:
            rid = input_int("预约ID: ", 1)
            r = reservation_manager.get_reservation_by_id(rid)
            if r:
                print_reservation_detail(r)
            else:
                print("预约不存在")


def create_reservation_ui():
    print("\n--- 创建设备预约 ---")
    code = input("设备编号: ").strip()
    eq = equipment_manager.get_equipment_by_code(code)
    if not eq:
        print("设备不存在")
        return
    schedule = equipment_manager.get_equipment_schedule(eq['id'])
    if schedule:
        print(f"\n⚠️  设备 {eq['code']} 已有排期:")
        print(f"{'来源':<6}{'开始':<14}{'结束':<14}{'状态':<10}{'客户'}")
        print("-" * 60)
        for s in schedule:
            print(f"{s['source']:<6}{s['start']:<14}{s['end']:<14}{s['status']:<10}{s['customer']}")

    print("\n请输入预约日期范围:")
    start_date, end_date = input_date_range("预约开始日期", "预约结束日期")

    ok, msg, _ = equipment_manager.check_time_conflicts(eq['id'], start_date, end_date)
    if not ok:
        print(f"\n❌ {msg}")
        return

    customers = rental_manager.list_customers()
    print(f"\n客户列表:")
    print(f"{'ID':<6}{'客户名称':<32}{'联系人':<12}")
    print("-" * 55)
    for c in customers:
        print(f"{c['id']:<6}{c['name']:<32}{c['contact']:<12}")
    customer_id = input_int("客户ID: ", 1)
    customer = rental_manager.get_customer_by_id(customer_id)
    if not customer:
        print("客户不存在")
        return

    print("\n租赁模式:")
    print("  1. 按天 (每日8小时)")
    print("  2. 按小时")
    mode_choice = input_int("请选择: ", 1, 2)
    rental_mode = '按天' if mode_choice == 1 else '按小时'

    if rental_mode == '按天':
        default_daily = eq['hourly_rate'] * 8
        daily_rate = input_float(f"预计每日租金 (默认{default_daily:.0f}元/天): ", 0) or default_daily
        hourly_rate = None
    else:
        hourly_rate = input_float(f"预计小时费率 (默认{eq['hourly_rate']:.0f}元/小时): ", 0) or eq['hourly_rate']
        daily_rate = None

    remarks = input("备注 (可选): ").strip()
    ok, rid, msg = reservation_manager.create_reservation(
        customer_id, eq['id'], start_date, end_date,
        rental_mode, daily_rate, hourly_rate, remarks
    )
    print(msg)


def convert_reservation_ui():
    print("\n--- 预约转正式租赁 ---")
    pending = reservation_manager.list_reservations()
    pending = [r for r in pending if r['status'] in ('待确认', '已确认')]
    if not pending:
        print("没有可转换的预约")
        return
    print_reservation_table(pending, "可转换预约")
    rid = input_int("选择预约ID: ", 1)
    r = reservation_manager.get_reservation_by_id(rid)
    if not r:
        print("预约不存在")
        return
    print(f"\n预约详情: 客户 {r['customer_name']}, 设备 {r['equipment_code']}, "
          f"{r['start_date']} ~ {r['end_date']}")
    eq = equipment_manager.get_equipment_by_id(r['equipment_id'])
    start_hours = input_float(f"起租时工时 (默认{int(eq['total_hours'])}): ", 0) or eq['total_hours']
    remarks = input("备注 (可选): ").strip()
    ok, rental_id, msg = reservation_manager.convert_reservation_to_rental(rid, start_hours, remarks)
    if ok:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")


def print_reservation_table(reservations, title):
    print(f"\n--- {title} ---")
    if not reservations:
        print("暂无记录")
        return
    print(f"{'ID':<6}{'设备编号':<10}{'类型':<8}{'客户':<18}{'开始':<14}{'结束':<14}{'模式':<6}{'状态'}")
    print("-" * 85)
    for r in reservations:
        print(f"{r['id']:<6}{r['equipment_code']:<10}{r['equipment_type']:<8}"
              f"{(r['customer_name'] or '')[:16]:<18}{r['start_date']:<14}{r['end_date']:<14}"
              f"{r['rental_mode']:<6}{r['status']}")


def print_reservation_detail(r):
    print("\n--- 预约详情 ---")
    print(f"预约ID: {r['id']}")
    print(f"状态: {r['status']}")
    print(f"设备: {r['equipment_code']} - {r['equipment_type']} {r['equipment_model']}")
    print(f"客户: {r['customer_name']} (联系人: {r['customer_contact']}, 电话: {r['customer_phone']})")
    print(f"预约期间: {r['start_date']} ~ {r['end_date']} ({equipment_manager.days_between(r['start_date'], r['end_date'])} 天)")
    print(f"租赁模式: {r['rental_mode']}")
    if r['rental_mode'] == '按天':
        print(f"预计日租金: ¥{r['expected_daily_rate']:.2f}/天")
    else:
        print(f"预计小时费率: ¥{r['expected_hourly_rate']:.2f}/小时")
    if r['remarks']:
        print(f"备注: {r['remarks']}")
    print(f"创建时间: {r['created_at']}")


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
    idle_equipments = equipment_manager.list_equipment()
    print(f"\n设备总览 (空闲设备自动标绿):")
    print_equipment_table(idle_equipments)

    code = input("\n设备编号: ").strip()
    eq = equipment_manager.get_equipment_by_code(code)
    if not eq:
        print("设备不存在")
        return

    ok, avail_msg = equipment_manager.is_available_for_rent(eq['id'])
    if not ok:
        print(f"\n❌ {avail_msg}")
        if eq['status'] == '待保养':
            print("  请先完成保养记录后再出租")
        schedule = equipment_manager.get_equipment_schedule(eq['id'])
        if schedule:
            print(f"  当前排期:")
            for s in schedule:
                print(f"    - {s['source']} {s['start']} ~ {s['end']} ({s['status']})")
        return

    customers = rental_manager.list_customers()
    print(f"\n客户列表:")
    print(f"{'ID':<6}{'客户名称':<32}{'联系人':<12}")
    print("-" * 55)
    for c in customers:
        print(f"{c['id']:<6}{c['name']:<32}{c['contact']:<12}")
    customer_id = input_int("客户ID: ", 1)
    customer = rental_manager.get_customer_by_id(customer_id)
    if not customer:
        print("客户不存在")
        return

    print("\n请输入租赁日期范围 (预计归还不能早于起租):")
    start_date, expected_return_date = input_date_range("起租日期", "预计归还日期", default_start_today=True)

    ok, conflict_msg, _ = equipment_manager.check_time_conflicts(eq['id'], start_date, expected_return_date)
    if not ok:
        print(f"\n❌ {conflict_msg}")
        print("请调整日期或创建预约。")
        return

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
    print(f"起租日期: {r['start_date']}")
    print(f"起租工时: {r['start_hours']:.1f}h")

    actual_return_date = input_date(
        "实际归还日期 (不能早于起租日)",
        default_today=True,
        not_before=r['start_date']
    )
    return_hours = input_float("归还时工时: ", min_val=r['start_hours'])

    fees = rental_manager.calculate_rental_fee(rid, actual_return_date, return_hours)
    if fees and 'error' in fees:
        print(f"\n⚠️  费用计算警告: {fees['error']}")
        confirm = input("是否继续? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

    if fees and 'error' not in fees:
        print(f"\n📋 费用预览:")
        print(f"  使用工时: {fees['used_hours']:.1f} 小时")
        print(f"  租赁天数: {fees['rental_days']} 天")
        print(f"  基本租金: ¥{fees['base_rent']:.2f}")
        if fees['overtime_fine'] > 0:
            print(f"  超期罚款: ¥{fees['overtime_fine']:.2f}")
        print(f"  总金额:   ¥{fees['total_amount']:.2f}")

        confirm = input(f"\n确认归还? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return

    ok, result = rental_manager.return_equipment(rid, actual_return_date, return_hours)
    if ok and isinstance(result, dict) and 'error' not in result:
        print("\n✅ 归还成功！")
        eq_after = equipment_manager.get_equipment_by_id(r['equipment_id'])
        print(f"  设备状态: {eq_after['status']}")
        if eq_after['status'] == '待保养':
            print(f"  ⚠️  设备已到保养周期，已自动标记为待保养，请尽快安排保养！")
        print(f"  基本租金: ¥{result['base_rent']:.2f}")
        if result['overtime_fine'] > 0:
            print(f"  超期罚款: ¥{result['overtime_fine']:.2f}")
        print(f"  总金额:   ¥{result['total_amount']:.2f}")
    else:
        print(f"❌ 归还失败: {result}")


def print_rental_table(rentals, title):
    print(f"\n--- {title} ---")
    if not rentals:
        print("暂无记录")
        return
    print(f"{'ID':<6}{'设备编号':<10}{'类型':<8}{'客户':<18}{'起租日期':<14}"
          f"{'预计归还':<14}{'模式':<6}{'状态':<8}{'总金额':>10}")
    print("-" * 100)
    for r in rentals:
        amount = f"¥{r['total_amount']:.0f}" if r['total_amount'] else '-'
        print(f"{r['id']:<6}{r['equipment_code']:<10}{r['equipment_type']:<8}"
              f"{(r['customer_name'] or '')[:16]:<18}{r['start_date']:<14}"
              f"{r['expected_return_date']:<14}{r['rental_mode']:<6}{r['status']:<8}{amount:>10}")


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
            "设备利用率报表(按类型+单台)",
            "月度保养费用统计",
            "导出每日状态报表(CSV)",
            "导出月度收入报表(CSV)",
            "导出设备利用率报表(CSV)",
        ])
        choice = input_int("请选择操作: ", 0, 8)

        if choice == 0:
            break
        elif choice == 1:
            stats = report_manager.get_equipment_status_by_type()
            print(f"\n{'设备类型':<10}{'总数':>6}{'在租':>6}{'空闲':>8}{'待保养':>8}{'保养中':>8}")
            print("-" * 55)
            total = {'总数': 0, '在租': 0, '空闲': 0, '待保养': 0, '保养中': 0}
            for eq_type, s in stats.items():
                print(f"{eq_type:<10}{s['总数']:>6}{s['在租']:>6}{s['空闲']:>8}"
                      f"{s['待保养']:>8}{s['保养中']:>8}")
                for k in total:
                    total[k] += s[k]
            print("-" * 55)
            print(f"{'合计':<10}{total['总数']:>6}{total['在租']:>6}{total['空闲']:>8}"
                  f"{total['待保养']:>8}{total['保养中']:>8}")

        elif choice == 2:
            report_date = input_date("报表日期", allow_empty=True, default_today=True)
            report = report_manager.get_daily_status_report(report_date)
            print(f"\n📅 每日设备状态报表 - {report['report_date']}")
            print(f"\n{'设备类型':<10}{'总数':>6}{'在租':>6}{'空闲':>8}{'待保养':>8}{'保养中':>8}")
            print("-" * 55)
            for eq_type, s in report['type_stats'].items():
                print(f"{eq_type:<10}{s['总数']:>6}{s['在租']:>6}{s['空闲']:>8}"
                      f"{s['待保养']:>8}{s['保养中']:>8}")
            print(f"\n设备明细:")
            print(f"{'编号':<10}{'类型':<8}{'状态':<10}{'客户':<18}{'起租':<14}"
                  f"{'预计归还':<14}{'工时':>10}{'距下次保养':>12}")
            print("-" * 100)
            for e in report['equipments']:
                hours_until = (e['maintenance_interval'] - (e['total_hours'] - e['last_maintenance_hours']))
                status_tag = e['status']
                if e['status'] == '待保养':
                    status_tag = '🔴待保养'
                print(f"{e['code']:<10}{e['type']:<8}{status_tag:<10}"
                      f"{(e['customer_name'] or '-')[:16]:<18}{(e['start_date'] or '-'):<14}"
                      f"{(e['expected_return_date'] or '-'):<14}{e['total_hours']:>8.1f}h{max(0, hours_until):>10.1f}h")

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
                print(f"{'客户名称':<28}{'租赁次数':>10}{'基本租金':>14}{'超期罚款':>14}{'总收入':>14}")
                print("-" * 85)
                for item in sorted(report['by_customer'], key=lambda x: x['总收入'], reverse=True):
                    print(f"{item['客户'][:26]:<28}{item['租赁次数']:>10}"
                          f"¥{item['基本租金']:>12.2f}¥{item['超期罚款']:>12.2f}¥{item['总收入']:>12.2f}")

            if report['by_type']:
                print(f"\n按设备类型汇总:")
                print(f"{'设备类型':<10}{'租赁次数':>10}{'总收入':>14}")
                print("-" * 40)
                for item in sorted(report['by_type'], key=lambda x: x['总收入'], reverse=True):
                    print(f"{item['设备类型']:<10}{item['租赁次数']:>10}¥{item['总收入']:>12.2f}")

        elif choice == 4:
            display_utilization_report()
        elif choice == 5:
            now = datetime.now()
            year = input_int(f"年份(默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份(默认{now.month}): ", 1, 12) or now.month
            summary = equipment_manager.get_maintenance_cost_summary(year, month)
            print(f"\n📋 {year}年{month}月保养费用统计")
            print(f"  保养次数: {summary['total_count']} 次")
            print(f"  总费用: ¥{summary['total_cost']:.2f}")
            if summary['by_type']:
                print("\n  按保养类型:")
                for t, data in summary['by_type'].items():
                    print(f"    - {t}: {data['次数']}次, ¥{data['费用']:.2f}")
            if summary['by_equipment']:
                print("\n  按设备:")
                for ec, data in sorted(summary['by_equipment'].items(),
                                       key=lambda x: x[1]['费用'], reverse=True):
                    print(f"    - {ec}({data['类型']}): {data['次数']}次, ¥{data['费用']:.2f}")

        elif choice == 6:
            report_date = input_date("报表日期", allow_empty=True, default_today=True)
            filepath = report_manager.export_daily_report_to_csv(report_date)
            print(f"✅ 报表已导出: {filepath}")
        elif choice == 7:
            now = datetime.now()
            year = input_int(f"年份 (默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份 (默认{now.month}): ", 1, 12) or now.month
            filepath = report_manager.export_monthly_report_to_csv(year, month)
            print(f"✅ 报表已导出: {filepath}")
        elif choice == 8:
            now = datetime.now()
            year = input_int(f"年份 (默认{now.year}): ", 2000, 2100) or now.year
            month = input_int(f"月份 (默认{now.month}): ", 1, 12) or now.month
            filepath = report_manager.export_utilization_report_to_csv(year, month)
            print(f"✅ 报表已导出: {filepath}")


def display_utilization_report():
    now = datetime.now()
    year = input_int(f"年份 (默认{now.year}): ", 2000, 2100) or now.year
    month = input_int(f"月份 (默认{now.month}): ", 1, 12) or now.month
    report = report_manager.get_utilization_report(year, month)
    s = report['summary']
    print(f"\n📊 设备利用率报表 - {year}年{month}月 ({s['days_in_month']}天)")
    print(f"\n总体:")
    print(f"  设备总数: {s['equipment_count']} 台")
    print(f"  总可用台天: {s['total_available_days']} 台天")
    print(f"  实际出租台天: {s['total_rented_days']} 台天")
    print(f"  整体平均利用率: {s['avg_utilization']:.2f}%")
    print(f"  累计收入: ¥{s['total_income']:.2f}")

    if report['by_type']:
        print(f"\n🔹 按设备类型 (利用率从高到低):")
        print(f"{'类型':<10}{'台数':>6}{'出租台天':>10}{'空闲台天':>10}"
              f"{'平均/台':>10}{'利用率':>10}{'收入':>12}")
        print("-" * 75)
        for t in report['by_type']:
            print(f"{t['type']:<10}{t['count']:>6}{t['rented_days']:>10}{t['idle_days']:>10}"
                  f"{t['avg_rented_days']:>9.1f}{t['utilization']:>9.2f}%¥{t['income']:>10.2f}")

    if report['by_equipment']:
        print(f"\n🔻 单台设备 (利用率从低到高，闲置设备先展示):")
        print(f"{'编号':<10}{'类型':<8}{'型号':<14}{'状态':<10}"
              f"{'出租':>6}{'空闲':>6}{'利用率':>10}{'收入':>12}{'提示'}")
        print("-" * 95)
        for e in report['by_equipment']:
            tip = ''
            if e['utilization'] < 20:
                tip = '⚠️严重闲置'
            elif e['utilization'] < 40:
                tip = '偏低'
            elif e['utilization'] >= 80:
                tip = '🔥高负荷'
            status_tag = e['status']
            if e['status'] == '待保养':
                status_tag = '🔴待保'
            print(f"{e['code']:<10}{e['type']:<8}{e['model'][:12]:<14}{status_tag:<10}"
                  f"{e['rented_days']:>6}{e['idle_days']:>6}"
                  f"{e['utilization']:>9.2f}%¥{e['income']:>10.2f} {tip}")


def main():
    init_db()
    db_exists = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db'))
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')

    equipment_manager.refresh_all_maintenance_statuses()

    if (not db_exists) or os.path.getsize(db_path) < 10000:
        print("首次运行，是否加载示例数据? (y/n): ", end='')
        if input().strip().lower() == 'y':
            seed_data.seed_sample_data()
            equipment_manager.refresh_all_maintenance_statuses()

    print_header("🏗️  工程机械租赁管理系统 v2.0 (增强版)")
    print("  日期校验 | 预约排期 | 保养状态流转 | 设备利用率")
    show_maintenance_alerts()

    while True:
        print_header("主菜单")
        print_menu([
            "设备管理",
            "客户管理",
            "预约排期管理",
            "租赁管理",
            "报表统计",
            "重新加载示例数据",
        ])
        choice = input_int("请选择操作: ", 0, 6)

        if choice == 0:
            print("\n👋 感谢使用，再见！")
            sys.exit(0)
        elif choice == 1:
            equipment_menu()
        elif choice == 2:
            customer_menu()
        elif choice == 3:
            reservation_menu()
        elif choice == 4:
            rental_menu()
        elif choice == 5:
            report_menu()
        elif choice == 6:
            confirm = input("确定重新加载示例数据? 这将覆盖所有现有数据 (y/n): ").strip().lower()
            if confirm == 'y':
                if os.path.exists(db_path):
                    os.remove(db_path)
                init_db()
                seed_data.seed_sample_data()
                equipment_manager.refresh_all_maintenance_statuses()


if __name__ == '__main__':
    main()
