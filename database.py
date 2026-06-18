import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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

    conn.commit()
    conn.close()
