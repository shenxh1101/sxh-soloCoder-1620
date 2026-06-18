from database import get_conn
from datetime import datetime, date

EQUIPMENT_TYPES = ['挖掘机', '装载机', '起重机', '压路机', '推土机']


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


def get_maintenance_alert_list():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, code, type, model, total_hours, last_maintenance_hours, maintenance_interval,
               (total_hours - last_maintenance_hours) as hours_since_maintenance,
               (maintenance_interval - (total_hours - last_maintenance_hours)) as hours_until_next
        FROM equipment
        WHERE (total_hours - last_maintenance_hours) >= maintenance_interval * 0.8
        ORDER BY hours_until_next ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_maintenance_record(eq_id, maintenance_date, hours_at_maintenance, m_type='常规保养', cost=0, remarks=''):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO maintenance (equipment_id, maintenance_date, hours_at_maintenance, type, cost, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (eq_id, maintenance_date, hours_at_maintenance, m_type, cost, remarks))
        cursor.execute('UPDATE equipment SET last_maintenance_hours = ? WHERE id = ?', (hours_at_maintenance, eq_id))
        conn.commit()
        return True, "保养记录添加成功"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def list_maintenance(eq_id=None):
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
    sql += ' ORDER BY m.maintenance_date DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
