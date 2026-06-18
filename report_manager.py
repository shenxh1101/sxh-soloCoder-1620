from database import get_conn
from datetime import datetime
import csv
import os
from equipment_manager import EQUIPMENT_TYPES


def get_equipment_status_by_type():
    conn = get_conn()
    cursor = conn.cursor()
    result = {}
    for eq_type in EQUIPMENT_TYPES:
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '在租'", (eq_type,))
        rented = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ? AND status = '空闲'", (eq_type,))
        idle = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE type = ?", (eq_type,))
        total = cursor.fetchone()[0]
        result[eq_type] = {'在租': rented, '空闲': idle, '总数': total}
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


def export_monthly_report_to_csv(year, month, output_dir=None):
    report = get_monthly_income_report(year, month)
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

        writer.writerow(['按设备类型汇总'])
        writer.writerow(['设备类型', '租赁次数', '总收入'])
        for item in report['by_type']:
            writer.writerow([
                item['设备类型'],
                item['租赁次数'],
                f"¥{item['总收入']:.2f}"
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
        writer.writerow(['设备类型', '总数', '在租', '空闲'])
        for eq_type, stats in report['type_stats'].items():
            writer.writerow([eq_type, stats['总数'], stats['在租'], stats['空闲']])
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
