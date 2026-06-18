from database import get_conn
from datetime import datetime, date, timedelta
import equipment_manager


def add_customer(name, contact, phone=''):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO customer (name, contact, phone)
            VALUES (?, ?, ?)
        ''', (name, contact, phone))
        conn.commit()
        customer_id = cursor.lastrowid
        return True, customer_id, f"客户添加成功，ID: {customer_id}"
    except Exception as e:
        return False, None, str(e)
    finally:
        conn.close()


def list_customers():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customer ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_customer_by_id(customer_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customer WHERE id = ?', (customer_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def search_customers(keyword):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM customer
        WHERE name LIKE ? OR contact LIKE ? OR phone LIKE ?
        ORDER BY name
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_rental(customer_id, equipment_id, start_date, expected_return_date,
                  start_hours, rental_mode='按天', daily_rate=None, hourly_rate=None, remarks=''):
    equipment = equipment_manager.get_equipment_by_id(equipment_id)
    if not equipment:
        return False, None, "设备不存在"

    ok, msg = equipment_manager.validate_date_range(start_date, expected_return_date)
    if not ok:
        return False, None, f"日期范围错误: {msg}"

    ok, avail_msg = equipment_manager.is_available_for_rent(equipment_id)
    if not ok:
        return False, None, avail_msg

    ok, conflict_msg, _ = equipment_manager.check_time_conflicts(
        equipment_id, start_date, expected_return_date
    )
    if not ok:
        return False, None, conflict_msg

    if rental_mode not in ['按天', '按小时']:
        return False, None, "租赁模式必须是 '按天' 或 '按小时'"

    if rental_mode == '按天' and daily_rate is None:
        daily_rate = equipment['hourly_rate'] * 8
    if rental_mode == '按小时' and hourly_rate is None:
        hourly_rate = equipment['hourly_rate']

    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO rental (customer_id, equipment_id, start_date, expected_return_date,
                               start_hours, rental_mode, daily_rate, hourly_rate, status, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '在租', ?)
        ''', (customer_id, equipment_id, start_date, expected_return_date,
              start_hours, rental_mode, daily_rate, hourly_rate, remarks))
        cursor.execute('UPDATE equipment SET status = ? WHERE id = ?', ('在租', equipment_id))
        conn.commit()
        rental_id = cursor.lastrowid
        return True, rental_id, f"租赁记录创建成功，ID: {rental_id}"
    except Exception as e:
        return False, None, str(e)
    finally:
        conn.close()


def calculate_rental_fee(rental_id, actual_return_date, return_hours):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rental WHERE id = ?', (rental_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    rental = dict(row)

    ok, msg = equipment_manager.validate_date_range(rental['start_date'], actual_return_date)
    if not ok:
        return {'error': f"归还日期错误: {msg}"}

    start_hours = rental['start_hours'] or 0
    if return_hours < start_hours:
        return {
            'error': (f"归还工时 ({return_hours:.1f}h) 不能小于起租工时 ({start_hours:.1f}h)，"
                      f"请检查录入是否正确")
        }

    if rental['rental_mode'] == '按天':
        rental_days = equipment_manager.days_between(rental['start_date'], actual_return_date)
        expected_days = equipment_manager.days_between(rental['start_date'], rental['expected_return_date'])
        base_rent = rental_days * (rental['daily_rate'] or 0)
        overtime_days = max(0, rental_days - expected_days)
        overtime_fine = overtime_days * (rental['daily_rate'] or 0) * 1.5
    else:
        used_hours = return_hours - start_hours
        expected_days = equipment_manager.days_between(rental['start_date'], rental['expected_return_date'])
        expected_hours = expected_days * 8
        base_rent = used_hours * (rental['hourly_rate'] or 0)
        overtime_hours = max(0, used_hours - expected_hours)
        overtime_fine = overtime_hours * (rental['hourly_rate'] or 0) * 1.5

    total_amount = base_rent + overtime_fine
    return {
        'base_rent': round(base_rent, 2),
        'overtime_fine': round(overtime_fine, 2),
        'total_amount': round(total_amount, 2),
        'used_hours': round(return_hours - start_hours, 2),
        'rental_days': equipment_manager.days_between(rental['start_date'], actual_return_date)
    }


def return_equipment(rental_id, actual_return_date, return_hours):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rental WHERE id = ?', (rental_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "租赁记录不存在"
    rental = dict(row)
    if rental['status'] == '已归还':
        conn.close()
        return False, "该租赁已归还"

    ok, _ = equipment_manager.validate_date_range(rental['start_date'], actual_return_date)
    if not ok:
        conn.close()
        return False, f"归还日期 [{actual_return_date}] 不能早于起租日期 [{rental['start_date']}]"

    if return_hours < (rental['start_hours'] or 0):
        conn.close()
        return False, (f"归还工时 ({return_hours:.1f}h) 不能小于起租工时 ({rental['start_hours']:.1f}h)")

    fees = calculate_rental_fee(rental_id, actual_return_date, return_hours)
    if not fees:
        conn.close()
        return False, "费用计算失败"
    if 'error' in fees:
        conn.close()
        return False, fees['error']

    try:
        cursor.execute('''
            UPDATE rental SET actual_return_date = ?, return_hours = ?,
                             base_rent = ?, overtime_fine = ?, total_amount = ?, status = '已归还'
            WHERE id = ?
        ''', (actual_return_date, return_hours, fees['base_rent'],
              fees['overtime_fine'], fees['total_amount'], rental_id))

        eq_id = rental['equipment_id']
        cursor.execute('SELECT total_hours, last_maintenance_hours, maintenance_interval FROM equipment WHERE id = ?', (eq_id,))
        eq = cursor.fetchone()
        hours_since = (return_hours or 0) - (eq['last_maintenance_hours'] or 0)
        needs_maint = hours_since >= eq['maintenance_interval']
        new_status = '待保养' if needs_maint else '空闲'

        cursor.execute('UPDATE equipment SET status = ?, total_hours = ? WHERE id = ?',
                       (new_status, return_hours, eq_id))
        conn.commit()
        return True, fees
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def list_rentals(status=None, customer_id=None, equipment_id=None,
                 start_date_from=None, start_date_to=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT r.*, c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM rental r
        LEFT JOIN customer c ON r.customer_id = c.id
        LEFT JOIN equipment e ON r.equipment_id = e.id
        WHERE 1=1
    '''
    params = []
    if status:
        sql += ' AND r.status = ?'
        params.append(status)
    if customer_id:
        sql += ' AND r.customer_id = ?'
        params.append(customer_id)
    if equipment_id:
        sql += ' AND r.equipment_id = ?'
        params.append(equipment_id)
    if start_date_from:
        sql += ' AND r.start_date >= ?'
        params.append(start_date_from)
    if start_date_to:
        sql += ' AND r.start_date <= ?'
        params.append(start_date_to)
    sql += ' ORDER BY r.created_at DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_rental_by_id(rental_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM rental r
        LEFT JOIN customer c ON r.customer_id = c.id
        LEFT JOIN equipment e ON r.equipment_id = e.id
        WHERE r.id = ?
    ''', (rental_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
