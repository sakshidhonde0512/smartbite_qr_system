import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Restaurant tables
cur.execute("""
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER
)
""")

# Menu table
cur.execute("""
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER,
    category TEXT,
    is_veg TEXT,
    allergens TEXT
)
""")

# Orders table
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER,
    item_name TEXT,
    quantity INTEGER,
    price INTEGER,
    status TEXT
)
""")

# Order items (group ordering + individual tracking)
cur.execute("""
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    item_name TEXT,
    quantity INTEGER,
    price INTEGER,
    user_name TEXT
)
""")

conn.commit()
conn.close()

print("Database created successfully")

DELETE FROM menu_items
WHERE id NOT IN (
    SELECT MIN(id)
    FROM menu_items
    GROUP BY name
);

def create_admin_table():
    conn = sqlite3.connect("cafe.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    cursor.execute("INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)",
                   ("admin", "admin123"))

    conn.commit()
    conn.close()

cur.execute("""
CREATE TABLE IF NOT EXISTS paid_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER,
    subtotal REAL,
    gst REAL,
    service_charge REAL,
    grand_total REAL,
    paid_at TEXT
)
""")