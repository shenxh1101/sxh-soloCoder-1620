from database import get_conn
from datetime import datetime, date

EQUIPMENT_TYPES = ['挖掘机', '装载机', '起重机', '压路机', '推土机']
AVAILABLE_FOR_RENT_STATUSES = ['空闲']
UNDER_MAINTENANCE_STATUSES = ['待保养', '保养中']


def _parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def validate_date_range(start_date_str, end_date_str):
    try:
        s = _parse_date(start_date_str)
        e = _parse_date(end_date_str)
    except ValueError:
        return False, "日期格式错误，请使用 YYYY-MM-DD"
    if e < s:
        return False, f"结束日期 [{end_date_str}] 不能早于开始日期 [{start_date_str}]"
    return True, ""


def days_between(start_date_str, end_date_str, inclusive=True):
    s = _parse_date(start_date_str)
    e = _parse_date(end_date_str)
    days = (e - s).days
    if inclusive:
        days += 1
    return days


def add_equipment(code, eq_type, model, hourly_rate, maintenance_interval=200):
    if eq_type not in EQUIPMENT_TYPES:
        return False, f"设备类型必须是: {', '.join(EQUIPMENT_TYPES)}"
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO equipment (code, type, model, hourly_rate, maintenance_interval)
            VALUES (?, ?, ?, ?, ?)
        ''', (code, eq_type, model, hourly_rate, maintenance_interval))
        conn.commit()
        return True, f"设备 {code} 添加成功"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def list_equipment(eq_type=None, status=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = 'SELECT * FROM equipment WHERE 1=1'
    params = []
    if eq_type:
        sql += ' AND type = ?'
        params.append(eq_type)
    if status:
        sql += ' AND status = ?'
        params.append(status)
    sql += ' ORDER BY type, code'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_equipment_by_id(eq_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM equipment WHERE id = ?', (eq_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_equipment_by_code(code):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM equipment WHERE code = ?', (code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_equipment_status(eq_id, status):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('UPDATE equipment SET status = ? WHERE id = ?', (status, eq_id))
    conn.commit()
    conn.close()


def update_equipment_hours(eq_id, hours):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('UPDATE equipment SET total_hours = ? WHERE id = ?', (hours, eq_id))
    conn.commit()
    conn.close()


def refresh_maintenance_status(eq_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM equipment WHERE id = ?', (eq_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    eq = dict(row)
    hours_since = (eq['total_hours'] or 0) - (eq['last_maintenance_hours'] or 0)
    needs_maintenance = hours_since >= eq['maintenance_interval']
    current_status = eq['status']
    new_status = current_status
    if needs_maintenance and current_status in ('空闲',):
        new_status = '待保养'
    elif (not needs_maintenance) and current_status == '待保养':
        new_status = '空闲'
    if new_status != current_status:
        cursor.execute('UPDATE equipment SET status = ? WHERE id = ?', (new_status, eq_id))
        conn.commit()
    conn.close()
    return new_status


def refresh_all_maintenance_statuses():
    all_eq = list_equipment()
    updated = []
    for eq in all_eq:
        old = eq['status']
        new = refresh_maintenance_status(eq['id'])
        if old != new:
            updated.append((eq['code'], old, new))
    return updated


def is_available_for_rent(eq_id):
    eq = get_equipment_by_id(eq_id)
    if not eq:
        return False, "设备不存在"
    if eq['status'] == '在租':
        return False, f"设备 {eq['code']} 当前在租"
    if eq['status'] == '待保养':
        hours_since = (eq['total_hours'] or 0) - (eq['last_maintenance_hours'] or 0)
        return False, (f"设备 {eq['code']} 已达保养周期 "
                       f"(已用 {hours_since:.1f}h / 周期 {eq['maintenance_interval']}h)，"
                       f"需保养后才能出租")
    if eq['status'] == '保养中':
        return False, f"设备 {eq['code']} 正在保养中"
    return True, eq['status']


def _check_rental_conflict(cursor, equipment_id, start_date, end_date, exclude_rental_id=None):
    sql = '''
        SELECT id, start_date, expected_return_date, actual_return_date, status
        FROM rental
        WHERE equipment_id = ?
          AND status != '已取消'
          AND (actual_return_date IS NULL OR actual_return_date >= ?)
          AND start_date <= ?
    '''
    params = [equipment_id, start_date, end_date]
    if exclude_rental_id:
        sql += ' AND id != ?'
        params.append(exclude_rental_id)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conflicts = []
    for r in rows:
        rd = r['actual_return_date'] or r['expected_return_date']
        if rd >= start_date and r['start_date'] <= end_date:
            conflicts.append({
                'type': '在租/历史租赁',
                'id': r['id'],
                'start': r['start_date'],
                'end': rd,
                'status': r['status'],
            })
    return conflicts


def _check_reservation_conflict(cursor, equipment_id, start_date, end_date, exclude_reservation_id=None):
    sql = '''
        SELECT id, start_date, end_date, status
        FROM reservation
        WHERE equipment_id = ?
          AND status IN ('待确认', '已确认')
          AND end_date >= ?
          AND start_date <= ?
    '''
    params = [equipment_id, start_date, end_date]
    if exclude_reservation_id:
        sql += ' AND id != ?'
        params.append(exclude_reservation_id)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conflicts = []
    for r in rows:
        if r['end_date'] >= start_date and r['start_date'] <= end_date:
            conflicts.append({
                'type': '预约',
                'id': r['id'],
                'start': r['start_date'],
                'end': r['end_date'],
                'status': r['status'],
            })
    return conflicts


def check_time_conflicts(equipment_id, start_date, end_date,
                         exclude_rental_id=None, exclude_reservation_id=None):
    ok, msg = validate_date_range(start_date, end_date)
    if not ok:
        return False, msg, []
    conn = get_conn()
    cursor = conn.cursor()
    rental_cf = _check_rental_conflict(cursor, equipment_id, start_date, end_date, exclude_rental_id)
    resv_cf = _check_reservation_conflict(cursor, equipment_id, start_date, end_date, exclude_reservation_id)
    conn.close()
    all_conflicts = rental_cf + resv_cf
    if all_conflicts:
        return False, _format_conflicts(all_conflicts), all_conflicts
    return True, "无时间冲突", []


def _format_conflicts(conflicts):
    lines = [f"存在 {len(conflicts)} 个时间冲突:"]
    for i, c in enumerate(conflicts, 1):
        lines.append(
            f"  {i}. [{c['type']}-{c['status']}] ID:{c['id']} "
            f"占用 {c['start']} ~ {c['end']}"
        )
    return "\n".join(lines)


def get_equipment_schedule(equipment_id, from_date=None, to_date=None):
    if from_date is None:
        from_date = datetime.now().strftime('%Y-%m-%d')
    if to_date is None:
        to_date = (datetime.now().date() + __import__('datetime').timedelta(days=90)).strftime('%Y-%m-%d')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT '租赁' as source_type, id, start_date,
               COALESCE(actual_return_date, expected_return_date) as end_date,
               status, customer_id
        FROM rental
        WHERE equipment_id = ?
          AND status != '已取消'
          AND COALESCE(actual_return_date, expected_return_date) >= ?
          AND start_date <= ?
    ''', (equipment_id, from_date, to_date))
    rentals = [dict(row) for row in cursor.fetchall()]
    cursor.execute('''
        SELECT '预约' as source_type, id, start_date, end_date,
               status, customer_id
        FROM reservation
        WHERE equipment_id = ?
          AND status IN ('待确认', '已确认')
          AND end_date >= ?
          AND start_date <= ?
    ''', (equipment_id, from_date, to_date))
    reservations = [dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT c.id, c.name FROM customer c')
    customer_map = {row['id']: row['name'] for row in cursor.fetchall()}
    conn.close()
    schedule = []
    for r in rentals + reservations:
        schedule.append({
            'source': r['source_type'],
            'id': r['id'],
            'start': r['start_date'],
            'end': r['end_date'],
            'status': r['status'],
            'customer': customer_map.get(r['customer_id'], '未知'),
        })
    schedule.sort(key=lambda x: x['start'])
    return schedule


def get_maintenance_alert_list():
    refresh_all_maintenance_statuses()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, code, type, model, total_hours, last_maintenance_hours, maintenance_interval, status,
               (total_hours - last_maintenance_hours) as hours_since_maintenance,
               (maintenance_interval - (total_hours - last_maintenance_hours)) as hours_until_next
        FROM equipment
        WHERE (total_hours - last_maintenance_hours) >= maintenance_interval * 0.8
           OR status IN ('待保养', '保养中')
        ORDER BY (total_hours - last_maintenance_hours) DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def start_maintenance(eq_id, maintenance_date=None):
    eq = get_equipment_by_id(eq_id)
    if not eq:
        return False, "设备不存在"
    if eq['status'] not in ('待保养', '空闲'):
        return False, f"设备当前状态 [{eq['status']}] 无法开始保养"
    if maintenance_date is None:
        maintenance_date = datetime.now().strftime('%Y-%m-%d')
    update_equipment_status(eq_id, '保养中')
    return True, f"设备 {eq['code']} 已进入保养状态"


def add_maintenance_record(eq_id, maintenance_date, hours_at_maintenance, m_type='常规保养', cost=0, remarks=''):
    eq = get_equipment_by_id(eq_id)
    if not eq:
        return False, None, "设备不存在"
    hours_since = (eq['total_hours'] or 0) - (eq['last_maintenance_hours'] or 0)
    hours_diff = hours_at_maintenance - (eq['last_maintenance_hours'] or 0)
    if hours_diff < 0:
        return False, None, f"保养工时 ({hours_at_maintenance}h) 不能小于上次保养工时 ({eq['last_maintenance_hours']}h)"
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO maintenance (equipment_id, maintenance_date, hours_at_maintenance, type, cost, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (eq_id, maintenance_date, hours_at_maintenance, m_type, cost, remarks))
        mid = cursor.lastrowid
        cursor.execute('UPDATE equipment SET last_maintenance_hours = ? WHERE id = ?', (hours_at_maintenance, eq_id))
        cursor.execute('SELECT status FROM equipment WHERE id = ?', (eq_id,))
        cur_status = cursor.fetchone()['status']
        new_status = cur_status
        if cur_status in ('保养中', '待保养'):
            new_status = '空闲'
            cursor.execute('UPDATE equipment SET status = ? WHERE id = ?', (new_status, eq_id))
        conn.commit()
        info = {
            'id': mid,
            'hours_since_last': hours_since,
            'prev_status': cur_status,
            'new_status': new_status,
        }
        return True, info, "保养记录添加成功"
    except Exception as e:
        return False, None, str(e)
    finally:
        conn.close()


def list_maintenance(eq_id=None, year=None, month=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT m.*, e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM maintenance m
        LEFT JOIN equipment e ON m.equipment_id = e.id
        WHERE 1=1
    '''
    params = []
    if eq_id:
        sql += ' AND m.equipment_id = ?'
        params.append(eq_id)
    if year:
        sql += ' AND strftime(\'%Y\', m.maintenance_date) = ?'
        params.append(f'{year:04d}')
    if month:
        sql += ' AND strftime(\'%m\', m.maintenance_date) = ?'
        params.append(f'{month:02d}')
    sql += ' ORDER BY m.maintenance_date DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_maintenance_cost_summary(year=None, month=None):
    records = list_maintenance(year=year, month=month)
    by_type = {}
    by_equipment = {}
    total = 0
    total_count = 0
    for r in records:
        t = r['type']
        ec = r['equipment_code']
        c = r['cost'] or 0
        total += c
        total_count += 1
        if t not in by_type:
            by_type[t] = {'次数': 0, '费用': 0}
        by_type[t]['次数'] += 1
        by_type[t]['费用'] += c
        if ec not in by_equipment:
            by_equipment[ec] = {'类型': r['equipment_type'], '次数': 0, '费用': 0}
        by_equipment[ec]['次数'] += 1
        by_equipment[ec]['费用'] += c
    return {
        'total_count': total_count,
        'total_cost': round(total, 2),
        'by_type': by_type,
        'by_equipment': by_equipment,
        'records': records,
    }


import calendar as _calendar


def get_equipment_calendar(equipment_id, year, month):
    _, days_in_month = _calendar.monthrange(year, month)
    month_start = _parse_date(f"{year}-{month:02d}-01")
    month_end = _parse_date(f"{year}-{month:02d}-{days_in_month}")

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_date,
               COALESCE(actual_return_date, expected_return_date) as end_date,
               status
        FROM rental
        WHERE equipment_id = ?
          AND status != '已取消'
          AND COALESCE(actual_return_date, expected_return_date) >= ?
          AND start_date <= ?
    ''', (equipment_id, month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
    rentals = [dict(row) for row in cursor.fetchall()]

    cursor.execute('''
        SELECT id, start_date, end_date, status
        FROM reservation
        WHERE equipment_id = ?
          AND status IN ('待确认', '已确认')
          AND end_date >= ?
          AND start_date <= ?
    ''', (equipment_id, month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
    reservations = [dict(row) for row in cursor.fetchall()]

    cursor.execute('''
        SELECT id, maintenance_date, hours_at_maintenance, type
        FROM maintenance
        WHERE equipment_id = ?
          AND strftime('%Y', maintenance_date) = ?
          AND strftime('%m', maintenance_date) = ?
    ''', (equipment_id, f'{year:04d}', f'{month:02d}'))
    maint_records = [dict(row) for row in cursor.fetchall()]
    maint_dates = set(m['maintenance_date'] for m in maint_records)

    conn.close()

    eq = get_equipment_by_id(equipment_id)

    calendar = []
    for day in range(1, days_in_month + 1):
        d = _parse_date(f"{year}-{month:02d}-{day:02d}")
        d_str = d.strftime('%Y-%m-%d')

        if d_str in maint_dates:
            status = '保养'
            detail = [f"保养记录: {', '.join(m['type'] for m in maint_records if m['maintenance_date'] == d_str)}"]
        else:
            status = '空闲'
            detail = []

        for r in rentals:
            rs = _parse_date(r['start_date'])
            re = _parse_date(r['end_date'])
            if rs <= d <= re:
                status = '在租' if r['status'] == '在租' else '已归还'
                detail.append(f"租赁#{r['id']}({r['status']})")
                break

        if status in ('空闲',):
            for rv in reservations:
                rs = _parse_date(rv['start_date'])
                re = _parse_date(rv['end_date'])
                if rs <= d <= re:
                    status = '预约'
                    detail.append(f"预约#{rv['id']}({rv['status']})")
                    break

        calendar.append({
            'day': day,
            'date': d_str,
            'status': status,
            'detail': detail,
            'weekday': d.weekday(),
        })

    return {
        'equipment': eq,
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
        'calendar': calendar,
    }


def get_type_availability_matrix(eq_type, year, month):
    _, days_in_month = _calendar.monthrange(year, month)
    month_start_str = f"{year}-{month:02d}-01"
    month_end_str = f"{year}-{month:02d}-{days_in_month}"

    equipments = list_equipment(eq_type=eq_type)
    result = []

    for eq in equipments:
        cal = get_equipment_calendar(eq['id'], year, month)
        free_days = []
        for day_info in cal['calendar']:
            if day_info['status'] == '空闲':
                free_days.append(day_info['day'])
        result.append({
            'code': eq['code'],
            'model': eq['model'],
            'status': eq['status'],
            'free_days': free_days,
            'free_count': len(free_days),
        })

    result.sort(key=lambda x: (-x['free_count'], x['code']))

    return {
        'eq_type': eq_type,
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
        'equipments': result,
    }
