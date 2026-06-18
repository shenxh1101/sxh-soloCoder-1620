from database import get_conn
from datetime import datetime
import equipment_manager
import rental_manager


def generate_settlement_from_rental(rental_id, maintenance_remark='', auto_settle=True):
    r = rental_manager.get_rental_by_id(rental_id)
    if not r:
        return False, None, "租赁记录不存在"
    if r['status'] != '已归还':
        return False, None, "租赁尚未归还，无法结算"

    start_hours = r['start_hours'] or 0
    end_hours = r['return_hours'] or 0
    used_hours = max(0, end_hours - start_hours)
    rental_days = equipment_manager.days_between(r['start_date'], r['actual_return_date'])
    expected_days = equipment_manager.days_between(r['start_date'], r['expected_return_date'])

    overtime_days = max(0, rental_days - expected_days)
    if r['rental_mode'] == '按天':
        overtime_hours = overtime_days * 8
    else:
        overtime_hours = max(0, used_hours - expected_days * 8)

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM settlement WHERE rental_id = ?', (rental_id,))
    existing = cursor.fetchone()

    if existing:
        settlement_id = existing['id']
        cursor.execute('''
            UPDATE settlement SET
                settlement_date = ?, start_date = ?, end_date = ?, rental_days = ?,
                start_hours = ?, end_hours = ?, used_hours = ?,
                rental_mode = ?, daily_rate = ?, hourly_rate = ?,
                base_rent = ?, overtime_days = ?, overtime_hours = ?, overtime_fine = ?,
                maintenance_remark = ?, total_amount = ?
            WHERE id = ?
        ''', (
            datetime.now().strftime('%Y-%m-%d'),
            r['start_date'], r['actual_return_date'], rental_days,
            start_hours, end_hours, used_hours,
            r['rental_mode'], r['daily_rate'], r['hourly_rate'],
            r['base_rent'] or 0, overtime_days, overtime_hours, r['overtime_fine'] or 0,
            maintenance_remark, r['total_amount'] or 0,
            settlement_id
        ))
    else:
        cursor.execute('''
            INSERT INTO settlement (
                rental_id, customer_id, equipment_id,
                settlement_date, start_date, end_date, rental_days,
                start_hours, end_hours, used_hours,
                rental_mode, daily_rate, hourly_rate,
                base_rent, overtime_days, overtime_hours, overtime_fine,
                maintenance_remark, total_amount, paid_amount, payment_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '未结清')
        ''', (
            rental_id, r['customer_id'], r['equipment_id'],
            datetime.now().strftime('%Y-%m-%d'),
            r['start_date'], r['actual_return_date'], rental_days,
            start_hours, end_hours, used_hours,
            r['rental_mode'], r['daily_rate'], r['hourly_rate'],
            r['base_rent'] or 0, overtime_days, overtime_hours, r['overtime_fine'] or 0,
            maintenance_remark, r['total_amount'] or 0
        ))
        settlement_id = cursor.lastrowid
        cursor.execute(
            'UPDATE rental SET settlement_id = ? WHERE id = ?',
            (settlement_id, rental_id)
        )

    conn.commit()
    conn.close()

    settlement = get_settlement_by_id(settlement_id)
    return True, settlement, "结算明细生成成功"


def get_settlement_by_id(settlement_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*,
               c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM settlement s
        LEFT JOIN customer c ON s.customer_id = c.id
        LEFT JOIN equipment e ON s.equipment_id = e.id
        WHERE s.id = ?
    ''', (settlement_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_settlement_by_rental_id(rental_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*,
               c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM settlement s
        LEFT JOIN customer c ON s.customer_id = c.id
        LEFT JOIN equipment e ON s.equipment_id = e.id
        WHERE s.rental_id = ?
    ''', (rental_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_settlements(customer_id=None, payment_status=None, year=None, month=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT s.*,
               c.name as customer_name, c.contact as customer_contact, c.phone as customer_phone,
               e.code as equipment_code, e.type as equipment_type, e.model as equipment_model
        FROM settlement s
        LEFT JOIN customer c ON s.customer_id = c.id
        LEFT JOIN equipment e ON s.equipment_id = e.id
        WHERE 1=1
    '''
    params = []
    if customer_id:
        sql += ' AND s.customer_id = ?'
        params.append(customer_id)
    if payment_status:
        sql += ' AND s.payment_status = ?'
        params.append(payment_status)
    if year:
        sql += " AND strftime('%Y', s.settlement_date) = ?"
        params.append(f'{year:04d}')
    if month:
        sql += " AND strftime('%m', s.settlement_date) = ?"
        params.append(f'{month:02d}')
    sql += ' ORDER BY s.settlement_date DESC, s.id DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def record_payment(settlement_id, amount, remarks=''):
    s = get_settlement_by_id(settlement_id)
    if not s:
        return False, "结算记录不存在"
    if amount <= 0:
        return False, "付款金额必须大于0"
    new_paid = (s['paid_amount'] or 0) + amount
    total = s['total_amount'] or 0
    if new_paid > total:
        return False, f"累计付款 (¥{new_paid:.2f}) 超过账单总额 (¥{total:.2f})"
    if abs(new_paid - total) < 0.01:
        new_status = '已结清'
    elif new_paid > 0:
        new_status = '部分结清'
    else:
        new_status = '未结清'

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE settlement SET paid_amount = ?, payment_status = ?,
                              remarks = COALESCE(remarks, '') || ?
        WHERE id = ?
    ''', (new_paid, new_status, (f"\n收款 ¥{amount:.2f}: {remarks}" if remarks else f"\n收款 ¥{amount:.2f}"), settlement_id))
    cursor.execute('UPDATE rental SET payment_status = ? WHERE settlement_id = ?', (new_status, settlement_id))
    conn.commit()
    conn.close()
    return True, f"收款记录成功，当前状态: {new_status} (已付 ¥{new_paid:.2f}/¥{total:.2f})"


def get_customer_billing_summary(customer_id=None):
    conn = get_conn()
    cursor = conn.cursor()
    sql = '''
        SELECT s.customer_id, c.name as customer_name,
               COUNT(s.id) as bill_count,
               SUM(s.total_amount) as total_billed,
               SUM(s.paid_amount) as total_paid,
               SUM(s.total_amount - s.paid_amount) as total_unpaid
        FROM settlement s
        LEFT JOIN customer c ON s.customer_id = c.id
        WHERE 1=1
    '''
    params = []
    if customer_id:
        sql += ' AND s.customer_id = ?'
        params.append(customer_id)
    sql += ' GROUP BY s.customer_id ORDER BY total_unpaid DESC'
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for k in ('total_billed', 'total_paid', 'total_unpaid'):
            d[k] = round(d[k] or 0, 2)
        result.append(d)

    grand = {
        'bill_count': sum(r['bill_count'] for r in result),
        'total_billed': round(sum(r['total_billed'] for r in result), 2),
        'total_paid': round(sum(r['total_paid'] for r in result), 2),
        'total_unpaid': round(sum(r['total_unpaid'] for r in result), 2),
    }
    conn.close()
    return result, grand


def print_settlement_detail(s):
    print()
    print("=" * 60)
    print(f"          🧾 租 赁 结 算 明 细 单  #{s['id']}")
    print("=" * 60)
    print(f"  结算日期:   {s['settlement_date']}")
    print(f"  客户名称:   {s['customer_name']}")
    print(f"  联 系 人:   {s['customer_contact']}  {s['customer_phone'] or ''}")
    print(f"  设备信息:   {s['equipment_code']} - {s['equipment_type']} {s['equipment_model']}")
    print("-" * 60)
    print(f"  起租日期:   {s['start_date']}")
    print(f"  归还日期:   {s['end_date']}")
    print(f"  租赁天数:   {s['rental_days']} 天")
    print(f"  起租工时:   {s['start_hours']:.1f} h")
    print(f"  归还工时:   {s['end_hours']:.1f} h")
    print(f"  使用工时:   {s['used_hours']:.1f} h")
    print(f"  租赁模式:   {s['rental_mode']}")
    if s['rental_mode'] == '按天':
        print(f"  每日租金:   ¥{s['daily_rate'] or 0:.2f} /天")
    else:
        print(f"  小时费率:   ¥{s['hourly_rate'] or 0:.2f} /小时")
    print("-" * 60)
    print(f"  基础租金:   ¥{s['base_rent'] or 0:.2f}")
    if s['overtime_fine'] and s['overtime_fine'] > 0:
        if s['rental_mode'] == '按天':
            print(f"  超期天数:   {s['overtime_days']} 天 (超期费率 1.5x)")
        else:
            print(f"  超期工时:   {s['overtime_hours']:.1f} h (超期费率 1.5x)")
        print(f"  超期罚款:   ¥{s['overtime_fine'] or 0:.2f}")
    if s['maintenance_remark']:
        print(f"  保养备注:   {s['maintenance_remark']}")
    print("=" * 60)
    print(f"  💰 总金额:   ¥{s['total_amount'] or 0:.2f}")
    print(f"  已付金额:   ¥{s['paid_amount'] or 0:.2f}")
    print(f"  未付金额:   ¥{(s['total_amount'] or 0) - (s['paid_amount'] or 0):.2f}")
    print(f"  收款状态:   {s['payment_status']}")
    print("=" * 60)
    if s['remarks']:
        print(f"  备注: {s['remarks']}")
