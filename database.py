import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')

EQUIPMENT_STATUSES = ['空闲', '在租', '待保养', '保养中']
PAYMENT_STATUSES = ['未结清', '已结清', '部分结清']


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def _migrate(cursor):
    if not _table_exists(cursor, 'reservation'):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                equipment_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                expected_daily_rate REAL,
                expected_hourly_rate REAL,
                rental_mode TEXT DEFAULT '按天',
                status TEXT DEFAULT '待确认',
                converted_rental_id INTEGER,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer(id),
                FOREIGN KEY (equipment_id) REFERENCES equipment(id)
            )
        ''')
    else:
        if not _column_exists(cursor, 'reservation', 'converted_rental_id'):
            cursor.execute('ALTER TABLE reservation ADD COLUMN converted_rental_id INTEGER')

    if not _table_exists(cursor, 'settlement'):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settlement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rental_id INTEGER NOT NULL UNIQUE,
                customer_id INTEGER NOT NULL,
                equipment_id INTEGER NOT NULL,
                settlement_date TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                rental_days INTEGER NOT NULL,
                start_hours REAL NOT NULL,
                end_hours REAL NOT NULL,
                used_hours REAL NOT NULL,
                rental_mode TEXT NOT NULL,
                daily_rate REAL,
                hourly_rate REAL,
                base_rent REAL NOT NULL,
                overtime_days INTEGER DEFAULT 0,
                overtime_hours REAL DEFAULT 0,
                overtime_fine REAL DEFAULT 0,
                maintenance_remark TEXT,
                total_amount REAL NOT NULL,
                paid_amount REAL DEFAULT 0,
                payment_status TEXT DEFAULT '未结清',
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rental_id) REFERENCES rental(id),
                FOREIGN KEY (customer_id) REFERENCES customer(id),
                FOREIGN KEY (equipment_id) REFERENCES equipment(id)
            )
        ''')

    if not _column_exists(cursor, 'rental', 'settlement_id'):
        cursor.execute('ALTER TABLE rental ADD COLUMN settlement_id INTEGER')
    if not _column_exists(cursor, 'rental', 'payment_status'):
        cursor.execute("ALTER TABLE rental ADD COLUMN payment_status TEXT DEFAULT '未结清'")
        cursor.execute("UPDATE rental SET payment_status = '已结清' WHERE status = '已归还' AND total_amount > 0")
        cursor.execute("UPDATE rental SET payment_status = '未结清' WHERE payment_status IS NULL")
    if not _column_exists(cursor, 'reservation', 'customer_id'):
        pass

    cursor.execute('UPDATE equipment SET status = ? WHERE status NOT IN (?, ?, ?, ?)',
                   ('空闲', '空闲', '在租', '待保养', '保养中'))

    cursor.execute("UPDATE rental SET payment_status = '未结清' WHERE payment_status IS NULL OR payment_status = ''")


def init_db():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            model TEXT NOT NULL,
            hourly_rate REAL NOT NULL,
            total_hours REAL DEFAULT 0,
            last_maintenance_hours REAL DEFAULT 0,
            maintenance_interval INTEGER DEFAULT 200,
            status TEXT DEFAULT '空闲',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rental (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            equipment_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            expected_return_date TEXT NOT NULL,
            actual_return_date TEXT,
            start_hours REAL NOT NULL,
            return_hours REAL,
            rental_mode TEXT DEFAULT '按天',
            daily_rate REAL,
            hourly_rate REAL,
            base_rent REAL DEFAULT 0,
            overtime_fine REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT '在租',
            settlement_id INTEGER,
            payment_status TEXT DEFAULT '未结清',
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customer(id),
            FOREIGN KEY (equipment_id) REFERENCES equipment(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maintenance_date TEXT NOT NULL,
            hours_at_maintenance REAL NOT NULL,
            type TEXT DEFAULT '常规保养',
            cost REAL DEFAULT 0,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (equipment_id) REFERENCES equipment(id)
        )
    ''')

    _migrate(cursor)

    conn.commit()
    conn.close()
