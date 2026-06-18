from database import get_conn
from datetime import datetime
import equipment_manager
import rental_manager

RESERVATION_STATUSES = ['待确认', '已确认', '已取消', '已转租赁']


def create_reservation(customer_id, equipment_id, start_date, end_date,
                       rental_mode='按天', expected_daily_rate=None,
                       expected_hourly_rate=None, remarks=''):
    eq = equipment_manager.get_equipment_by_id(equipment_id)
    if not eq:
        return False, None, "设备不存在"
    customer = rental_manager.get_customer_by_id(customer_id)
    if not customer:
        return False, None, "客户不存在"
    ok, msg, conflicts = equipment_manager.check_time_conflicts(equipment_id, start_date, end_date)
    if not ok:
        return False, None, msg
    if rental_mode not in ('按天', '按小时'):
        return False, None, "租赁模式必须是 '按天' 或 '按小时'"
    if rental_mode == '按天' and expected_daily_rate is None:
        expected_daily_rate = eq['hourly_rate'] * 8
    if rental_mode == '按小时' and expected_hourly_rate is None:
        expected_hourly_rate = eq['hourly_rate']
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO reservation (customer_id, equipment_id, start_date, end_date,
                                     expected_daily_rate, expected_hourly_rate, rental_mode,
                                     status, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, '待确认', ?)
        ''', (customer_id, equipment_id, start_date, end_date,
              expected_daily_rate, expected_hourly_rate, rental_mode, remarks))
        conn.commit()
        rid = cursor.lastrowid
        return True, rid, f"预约创建成功，ID: {rid}"
    except Exception as e:
        return False, None, str(e)
    finally:
        conn.close()


def update_reservation_status(reservation_id, new_status):
    if new_status not in RESERVATION_STATUSES:
        return False, f"状态必须是: {', '.join(RESERVATION_STATUSES)}"
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reservation WHERE id = ?', (reservation_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "预约记录不存在"
    cursor.execute('UPDATE reservation SET status = ? WHERE id = ?', (new_status, reservation_id))
    conn.commit()
    conn.close()
    return True, f"预约状态已更新为: {new_status}"


def cancel_reservation(reservation_id, reason=''):
    ok, msg = update_reservation_status(reservation_id, '已取消')
    if ok and reason:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT remarks FROM reservation WHERE id = ?', (reservation_id,))
        cur = cursor.fetchone()['remarks'] or ''
        new_remarks = cur + f"\n取消原因: {reason}" if cur else f"取消原因: {reason}"
        cursor.execute('UPDATE reservation SET remarks = ? WHERE id = ?', (new_remarks, reservation_id))
        conn.commit()
        conn.close()
    return ok, msg


def confirm_reservation(reservation_id):
    r = get_reservation_by_id(reservation_id)
    if not r:
        return False, "预约不存在"
    ok, msg, conflicts = equipment_manager.check_time_conflicts(
        r['equipment_id'], r['start_date'], r['end_date'],
        exclude_reservation_id=reservation_id
    )
    if not ok:
        return False, f"确认失败，存在时间冲突:\n{msg}"
    return update_reservation_status(reservation_id, '已确认')


def convert_reservation_to_rental(reservation_id, start_hours, remarks=''):
    r = get_reservation_by_id(reservation_id)
    if not r:
        return False, None, "预约不存在"
    if r['status'] not in ('待确认', '已确认'):
        return False, None, f"当前状态 [{r['status']}] 无法转为租赁"
    eq = equipment_manager.get_equipment_by_id(r['equipment_id'])
    ok, avail_msg = equipment_manager.is_available_for_rent(r['equipment_id'])
    if not ok:
        return False, None, avail_msg
    ok, msg, conflicts = equipment_manager.check_time_conflicts(
        r['equipment_id'], r['start_date'], r['end_date'],
        exclude_reservation_id=reservation_id
    )
    if not ok:
        return False, None, f"时间冲突:\n{msg}"
    ok, rid, create_msg = rental_manager.create_rental(
        customer_id=r['customer_id'],
        equipment_id=r['equipment_id'],
        start_date=r['start_date'],
        expected_return_date=r['end_date'],
        start_hours=start_hours,
        rental_mode=r['rental_mode'],
        daily_rate=r['expected_daily_rate'],
        hourly_rate=r['expected_hourly_rate'],
        remarks=(r['remarks'] or '') + (f"\n{remarks}" if remarks else '')
    )
    if not ok:
        return False, None, create_msg
    update_reservation_status(reservation_id, '已转租赁')
    return True, rid, f"预约已转为租赁，租赁ID: {rid}"


def list_reservations(status=None, customer_id=None, equipment_id=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT rv.*, c.name as customer_name, c.contact as customer_contact,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM reservation rv
        LEFT JOIN customer c ON rv.customer_id = c.id
        LEFT JOIN equipment e ON rv.equipment_id = e.id
        WHERE 1=1
    '''
    params = []
    if status:
        sql += ' AND rv.status = ?'
        params.append(status)
    if customer_id:
        sql += ' AND rv.customer_id = ?'
        params.append(customer_id)
    if equipment_id:
        sql += ' AND rv.equipment_id = ?'
        params.append(equipment_id)
    sql += ' ORDER BY rv.start_date DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_reservation_by_id(reservation_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rv.*, c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model,
               e.hourly_rate as equipment_hourly_rate
        FROM reservation rv
        LEFT JOIN customer c ON rv.customer_id = c.id
        LEFT JOIN equipment e ON rv.equipment_id = e.id
        WHERE rv.id = ?
    ''', (reservation_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_upcoming_reservations(days=30, equipment_id=None):
    today = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now().date() + __import__('datetime').timedelta(days=days)).strftime('%Y-%m-%d')
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT rv.*, c.name as customer_name,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM reservation rv
        LEFT JOIN customer c ON rv.customer_id = c.id
        LEFT JOIN equipment e ON rv.equipment_id = e.id
        WHERE rv.status IN ('待确认', '已确认')
          AND rv.end_date >= ?
          AND rv.start_date <= ?
    '''
    params = [today, future]
    if equipment_id:
        sql += ' AND rv.equipment_id = ?'
        params.append(equipment_id)
    sql += ' ORDER BY rv.start_date ASC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
