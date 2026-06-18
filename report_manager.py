from database import get_conn
from datetime import datetime
import calendar
import csv
import os
from equipment_manager import EQUIPMENT_TYPES
import equipment_manager


def _parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


def _overlap_days(start1, end1, start2, end2):
    s = max(start1, start2)
    e = min(end1, end2)
    if e < s:
        return 0
    return (e - s).days + 1


def get_equipment_status_by_type():
    conn = get_conn()
    cursor = conn.cursor()
    result = {}
    for eq_type in EQUIPMENT_TYPES:
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '在租'", (eq_type,))
        rented = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '空闲'", (eq_type,))
        idle = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '待保养'", (eq_type,))
        maint_needed = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '保养中'", (eq_type,))
        mainting = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ?", (eq_type,))
        total = cursor.fetchone()[0]
        result[eq_type] = {'在租': rented, '空闲': idle,
                           '待保养': maint_needed, '保养中': mainting, '总数': total}
    conn.close()
    return result


def get_daily_status_report(report_date=None):
    if not report_date:
        report_date = datetime.now().strftime('%Y-%m-%d')
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT e.*, r.id as rental_id, r.customer_id, c.name as customer_name,
               r.start_date, r.expected_return_date
        FROM equipment e
        LEFT JOIN rental r ON e.id = r.equipment_id AND r.status = '在租'
        LEFT JOIN customer c ON r.customer_id = c.id
        ORDER BY e.type, e.code
    ''')
    rows = cursor.fetchall()
    conn.close()

    equipments = [dict(row) for row in rows]
    type_stats = get_equipment_status_by_type()

    return {
        'report_date': report_date,
        'equipments': equipments,
        'type_stats': type_stats
    }


def get_monthly_income_report(year, month):
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT r.*, c.name as customer_name, e.code as equipment_code,
               e.type as equipment_type, e.model as equipment_model
        FROM rental r
        LEFT JOIN customer c ON r.customer_id = c.id
        LEFT JOIN equipment e ON r.equipment_id = e.id
        WHERE r.status = '已归还'
          AND r.actual_return_date >= ?
          AND r.actual_return_date < ?
        ORDER BY r.actual_return_date
    ''', (start_date, end_date))
    rows = cursor.fetchall()

    rentals = [dict(row) for row in rows]

    by_customer = {}
    by_type = {}
    total_income = 0
    total_rent = 0
    total_fine = 0

    for r in rentals:
        customer = r['customer_name'] or '未知客户'
        eq_type = r['equipment_type'] or '未知类型'
        total_income += r['total_amount'] or 0
        total_rent += r['base_rent'] or 0
        total_fine += r['overtime_fine'] or 0

        if customer not in by_customer:
            by_customer[customer] = {
                '客户': customer,
                '租赁次数': 0,
                '基本租金': 0,
                '超期罚款': 0,
                '总收入': 0
            }
        by_customer[customer]['租赁次数'] += 1
        by_customer[customer]['基本租金'] += r['base_rent'] or 0
        by_customer[customer]['超期罚款'] += r['overtime_fine'] or 0
        by_customer[customer]['总收入'] += r['total_amount'] or 0

        if eq_type not in by_type:
            by_type[eq_type] = {
                '设备类型': eq_type,
                '租赁次数': 0,
                '总收入': 0
            }
        by_type[eq_type]['租赁次数'] += 1
        by_type[eq_type]['总收入'] += r['total_amount'] or 0

    conn.close()

    return {
        'year': year,
        'month': month,
        'rentals': rentals,
        'by_customer': list(by_customer.values()),
        'by_type': list(by_type.values()),
        'summary': {
            '租赁总数': len(rentals),
            '基本租金合计': round(total_rent, 2),
            '超期罚款合计': round(total_fine, 2),
            '总收入合计': round(total_income, 2)
        }
    }


def get_utilization_report(year, month):
    _, days_in_month = calendar.monthrange(year, month)
    month_start = _parse_date(f"{year}-{month:02d}-01")
    month_end = _parse_date(f"{year}-{month:02d}-{days_in_month}")
    today = datetime.now().date()
    effective_end = min(month_end, today)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM equipment ORDER BY type, code')
    all_eq = [dict(row) for row in cursor.fetchall()]

    start_str = f"{year}-{month:02d}-01"
    if month == 12:
        end_str = f"{year + 1}-01-01"
    else:
        end_str = f"{year}-{month + 1:02d}-01"

    cursor.execute('''
        SELECT r.*, e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM rental r
        LEFT JOIN equipment e ON r.equipment_id = e.id
        WHERE r.status != '已取消'
          AND r.start_date <= ?
          AND (r.actual_return_date IS NULL OR r.actual_return_date >= ?)
    ''', (end_str[:7] + "-31" if False else end_str, start_str))
    all_rentals = [dict(row) for row in cursor.fetchall()]

    conn.close()

    per_equipment = []
    for eq in all_eq:
        eq_rentals = [r for r in all_rentals if r['equipment_id'] == eq['id']]
        rented_days = 0
        income = 0
        rental_count = 0
        for r in eq_rentals:
            r_start = _parse_date(r['start_date'])
            full_end_str = r['actual_return_date'] or r['expected_return_date']
            r_full_end = _parse_date(full_end_str)
            total_rental_days = (r_full_end - r_start).days + 1

            overlap_start = max(r_start, month_start)
            if r['status'] == '在租':
                overlap_end = min(r_full_end, effective_end)
            else:
                overlap_end = min(r_full_end, month_end)
            if overlap_end < overlap_start:
                continue
            overlap = (overlap_end - overlap_start).days + 1
            rented_days += overlap
            rental_count += 1

            if r['rental_mode'] == '按天':
                daily = r['daily_rate'] or 0
                month_income = overlap * daily
            else:
                hourly = r['hourly_rate'] or 0
                month_income = overlap * 8 * hourly

            if r['status'] == '已归还':
                overtime_fine = r['overtime_fine'] or 0
                if overtime_fine > 0 and total_rental_days > 0:
                    expected_days = equipment_manager.days_between(
                        r['start_date'], r['expected_return_date']
                    )
                    actual_days = equipment_manager.days_between(
                        r['start_date'], r['actual_return_date']
                    )
                    overtime_real_days = max(0, actual_days - expected_days)
                    if overtime_real_days > 0:
                        ot_overlap_start = max(
                            overlap_start,
                            _parse_date(r['expected_return_date'])
                        )
                        ot_overlap_end = overlap_end
                        if ot_overlap_end >= ot_overlap_start:
                            ot_overlap = (ot_overlap_end - ot_overlap_start).days + 1
                            fine_per_day = overtime_fine / overtime_real_days
                            month_income += round(ot_overlap * fine_per_day, 2)

            income += round(month_income, 2)

        idle_days = days_in_month - rented_days
        utilization = (rented_days / days_in_month * 100) if days_in_month > 0 else 0

        per_equipment.append({
            'code': eq['code'],
            'type': eq['type'],
            'model': eq['model'],
            'status': eq['status'],
            'total_hours': eq['total_hours'] or 0,
            'rented_days': rented_days,
            'idle_days': max(0, idle_days),
            'total_days': days_in_month,
            'utilization': round(utilization, 2),
            'rental_count': rental_count,
            'income': round(income, 2),
        })

    per_type = {}
    for item in per_equipment:
        t = item['type']
        if t not in per_type:
            per_type[t] = {
                'type': t,
                'count': 0,
                'total_rented_days': 0,
                'total_idle_days': 0,
                'total_income': 0,
                'rental_count': 0,
            }
        per_type[t]['count'] += 1
        per_type[t]['total_rented_days'] += item['rented_days']
        per_type[t]['total_idle_days'] += item['idle_days']
        per_type[t]['total_income'] += item['income']
        per_type[t]['rental_count'] += item['rental_count']

    type_list = []
    for t, data in per_type.items():
        total_avail_days = data['count'] * days_in_month
        util = (data['total_rented_days'] / total_avail_days * 100) if total_avail_days > 0 else 0
        type_list.append({
            'type': t,
            'count': data['count'],
            'rented_days': data['total_rented_days'],
            'idle_days': data['total_idle_days'],
            'avg_rented_days': round(data['total_rented_days'] / data['count'], 1) if data['count'] else 0,
            'utilization': round(util, 2),
            'rental_count': data['rental_count'],
            'income': round(data['total_income'], 2),
        })
    type_list.sort(key=lambda x: x['utilization'], reverse=True)

    per_equipment.sort(key=lambda x: x['utilization'])

    grand_total_rented = sum(i['rented_days'] for i in per_equipment)
    grand_total_avail = len(per_equipment) * days_in_month
    grand_total_income = sum(i['income'] for i in per_equipment)
    grand_util = (grand_total_rented / grand_total_avail * 100) if grand_total_avail > 0 else 0

    summary = {
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
        'equipment_count': len(per_equipment),
        'total_rented_days': grand_total_rented,
        'total_available_days': grand_total_avail,
        'total_income': round(grand_total_income, 2),
        'avg_utilization': round(grand_util, 2),
    }

    return {
        'summary': summary,
        'by_type': type_list,
        'by_equipment': per_equipment,
    }


def export_utilization_report_to_csv(year, month, output_dir=None):
    report = get_utilization_report(year, month)
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    filename = f"设备利用率报表_{year}年{month:02d}月.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        s = report['summary']
        writer.writerow([f"设备利用率报表 - {year}年{month}月"])
        writer.writerow([])
        writer.writerow(['总体概况'])
        writer.writerow(['指标', '数值'])
        writer.writerow(['统计天数', f"{s['days_in_month']} 天"])
        writer.writerow(['设备总数', s['equipment_count']])
        writer.writerow(['总可用设备天数', f"{s['total_available_days']} 台天"])
        writer.writerow(['实际出租台天数', f"{s['total_rented_days']} 台天"])
        writer.writerow(['累计收入', f"¥{s['total_income']:.2f}"])
        writer.writerow(['整体平均利用率', f"{s['avg_utilization']:.2f}%"])
        writer.writerow([])

        writer.writerow(['按设备类型汇总 (利用率从高到低)'])
        writer.writerow([
            '设备类型', '台数', '出租台天', '空闲台天', '平均出租天数/台',
            '类型利用率', '租赁次数', '收入'
        ])
        for t in report['by_type']:
            writer.writerow([
                t['type'], t['count'], t['rented_days'], t['idle_days'],
                t['avg_rented_days'], f"{t['utilization']:.2f}%",
                t['rental_count'], f"¥{t['income']:.2f}"
            ])
        writer.writerow([])

        writer.writerow(['单台设备明细 (利用率从低到高，方便识别闲置)'])
        writer.writerow([
            '设备编号', '类型', '型号', '当前状态', '累计工时',
            '出租天数', '空闲天数', '利用率', '租赁次数', '收入', '闲置提示'
        ])
        for e in report['by_equipment']:
            tip = ''
            if e['utilization'] < 20:
                tip = '严重闲置⚠️'
            elif e['utilization'] < 40:
                tip = '使用率偏低'
            elif e['utilization'] >= 80:
                tip = '高负荷'
            writer.writerow([
                e['code'], e['type'], e['model'], e['status'], f"{e['total_hours']:.1f}h",
                e['rented_days'], e['idle_days'], f"{e['utilization']:.2f}%",
                e['rental_count'], f"¥{e['income']:.2f}", tip
            ])
    return filepath


def export_monthly_report_to_csv(year, month, output_dir=None):
    report = get_monthly_income_report(year, month)
    util_report = get_utilization_report(year, month)
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))

    filename = f"月度租赁收入报表_{year}年{month:02d}月.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        writer.writerow([f"月度租赁收入报表 - {year}年{month}月"])
        writer.writerow([])

        writer.writerow(['汇总统计'])
        writer.writerow(['指标', '数值'])
        writer.writerow(['租赁总数', report['summary']['租赁总数']])
        writer.writerow(['基本租金合计', f"¥{report['summary']['基本租金合计']:.2f}"])
        writer.writerow(['超期罚款合计', f"¥{report['summary']['超期罚款合计']:.2f}"])
        writer.writerow(['总收入合计', f"¥{report['summary']['总收入合计']:.2f}"])
        writer.writerow([])

        writer.writerow(['按客户汇总'])
        writer.writerow(['客户名称', '租赁次数', '基本租金', '超期罚款', '总收入'])
        for item in report['by_customer']:
            writer.writerow([
                item['客户'],
                item['租赁次数'],
                f"¥{item['基本租金']:.2f}",
                f"¥{item['超期罚款']:.2f}",
                f"¥{item['总收入']:.2f}"
            ])
        writer.writerow([])

        writer.writerow(['按设备类型汇总(收入)'])
        writer.writerow(['设备类型', '租赁次数', '总收入'])
        for item in report['by_type']:
            writer.writerow([
                item['设备类型'],
                item['租赁次数'],
                f"¥{item['总收入']:.2f}"
            ])
        writer.writerow([])

        writer.writerow([
            '设备利用率汇总',
            f"(整体利用率 {util_report['summary']['avg_utilization']:.2f}%)"
        ])
        writer.writerow(['设备类型', '台数', '出租台天', '类型利用率', '收入'])
        for t in util_report['by_type']:
            writer.writerow([
                t['type'], t['count'], t['rented_days'],
                f"{t['utilization']:.2f}%", f"¥{t['income']:.2f}"
            ])
        writer.writerow([])

        writer.writerow(['租赁明细'])
        writer.writerow([
            '租赁ID', '客户名称', '设备编号', '设备类型', '设备型号',
            '起租日期', '归还日期', '租赁模式', '使用工时',
            '基本租金', '超期罚款', '总收入'
        ])
        for r in report['rentals']:
            used_hours = (r['return_hours'] or 0) - (r['start_hours'] or 0)
            writer.writerow([
                r['id'],
                r['customer_name'],
                r['equipment_code'],
                r['equipment_type'],
                r['equipment_model'],
                r['start_date'],
                r['actual_return_date'],
                r['rental_mode'],
                f"{used_hours:.1f}h",
                f"¥{r['base_rent']:.2f}",
                f"¥{r['overtime_fine']:.2f}",
                f"¥{r['total_amount']:.2f}"
            ])

    return filepath


def export_daily_report_to_csv(report_date=None, output_dir=None):
    report = get_daily_status_report(report_date)
    if report_date is None:
        report_date = report['report_date']
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))

    filename = f"每日设备状态报表_{report_date}.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        writer.writerow([f"每日设备状态报表 - {report_date}"])
        writer.writerow([])

        writer.writerow(['按设备类型统计'])
        writer.writerow(['设备类型', '总数', '在租', '空闲', '待保养', '保养中'])
        for eq_type, stats in report['type_stats'].items():
            writer.writerow([eq_type, stats['总数'], stats['在租'], stats['空闲'],
                             stats['待保养'], stats['保养中']])
        writer.writerow([])

        writer.writerow(['设备明细'])
        writer.writerow([
            '设备编号', '设备类型', '型号', '小时费率', '累计工时',
            '状态', '当前客户', '起租日期', '预计归还日期',
            '距上次保养工时', '下次保养剩余工时'
        ])
        for e in report['equipments']:
            hours_since = (e['total_hours'] or 0) - (e['last_maintenance_hours'] or 0)
            hours_until = (e['maintenance_interval'] or 200) - hours_since
            writer.writerow([
                e['code'],
                e['type'],
                e['model'],
                f"¥{e['hourly_rate']:.2f}/h",
                f"{e['total_hours'] or 0:.1f}h",
                e['status'],
                e['customer_name'] or '-',
                e['start_date'] or '-',
                e['expected_return_date'] or '-',
                f"{hours_since:.1f}h",
                f"{max(0, hours_until):.1f}h"
            ])

    return filepath
