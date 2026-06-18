import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')

EQUIPMENT_STATUSES = ['空闲', '在租', '待保养', '保养中']


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
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer(id),
                FOREIGN KEY (equipment_id) REFERENCES equipment(id)
            )
        ''')

    cursor.execute('UPDATE equipment SET status = ? WHERE status NOT IN (?, ?, ?, ?)',
                   ('空闲', '空闲', '在租', '待保养', '保养中'))


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
