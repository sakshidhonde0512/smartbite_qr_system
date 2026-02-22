from flask import Flask, request, jsonify,render_template,session, redirect,url_for
from flask_cors import CORS
import sqlite3
import json
import random
from datetime import datetime
from ai_engine import recommend
from flask import g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect("database.db")
    return g.db

print("🔥 THIS IS THE RUNNING app.py FILE 🔥")

app = Flask(__name__)
app.secret_key = "your_super_secret_key"
CORS(app)
conn = sqlite3.connect("database.db", check_same_thread=False,isolation_level=None)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

import os
print("DB PATH:", os.path.abspath("database.db"))

def get_db():
    conn = sqlite3.connect("database.db", timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
def get_db_connection():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    return conn
def get_db():
    return sqlite3.connect("database.db")

def init_bill_table():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bill_status (
        table_no INTEGER PRIMARY KEY,
        bill_generated INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_bill_table()

def create_payment_table():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paid_bill_id INTEGER,
        table_no INTEGER,
        amount REAL,
        payment_mode TEXT,
        transaction_id TEXT,
        payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paid_bill_id) REFERENCES paid_bills(id)
    )
    """)

    conn.commit()
    conn.close()

create_payment_table()

# conn = sqlite3.connect("database.db")
# cur = conn.cursor()

# # cur.execute("DROP TABLE IF EXISTS paid_bills")

# conn.commit()
# conn.close()

conn = sqlite3.connect("database.db")
cur = conn.cursor()

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

conn.commit()
conn.close()

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "customer":
            return "Access denied. Please scan QR again."
        return f(*args, **kwargs)
    return decorated_function

# @app.route("/")
# def home():
#     table_number = request.args.get("table")

#     if table_number:
#         session.clear()
#         session["role"] = "customer"
#         session["table_no"] = table_no
#         # return redirect(url_for("menu"))   # your existing menu route

#     return render_template("home.html")

# Get Menu
# @app.route("/menu", methods=["GET"])
# def get_menu():
#     con = get_db()
#     cur = con.cursor()
#     cur.execute("SELECT * FROM menu_items")
#     items = cur.fetchall()
#     con.close()

#     menu = []
#     for i in items:
#         menu.append({
#             "id": i[0],
#             "name": i[1],
#             "price": i[2],
#             "category": i[3],
#             "is_veg": i[4],
#             "allergens": i[5]
#         })

#     return jsonify(menu)

@app.route("/")
def index():
    table = request.args.get("table")

    if table:
        session.clear()
        session["role"] = "customer"
        session["table_no"] = table
        return redirect(url_for("menu",table_no=table))  # Use your existing menu route name

    return render_template("home.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Backend validation
        if not username or not password:
            error = "All fields are required"

        elif len(username) < 4:
            error = "Username must be at least 4 characters"

        elif len(password) < 6:
            error = "Password must be at least 6 characters"

        elif username == "smart_admin" and password == "admin0512":
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))

        else:
            error = "Invalid Credentials"

    return render_template("admin_login.html", error=error)
@app.route('/api/menu')
def api_menu():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT DISTINCT
            c.id AS category_id, 
            c.name AS category_name,
            sc.id AS sub_id, 
            sc.name AS sub_name,
            m.id AS item_id,
            m.name AS item_name,
            m.price,
            m.is_veg,
            m.contains_dairy,
            m.contains_nuts,
            m.is_gluten_free
        FROM categories c
        JOIN sub_categories sc ON sc.category_id = c.id
        LEFT JOIN menu_items m ON m.sub_category_id = sc.id
        AND m.available = 1
        ORDER BY c.id, sc.id, m.id
    """).fetchall()

    menu = {}

    for r in rows:
        cat_id = r["category_id"]
        sub_id = r["sub_id"]

        if cat_id not in menu:
            menu[cat_id] = {
                "id": cat_id,
                "name": r["category_name"],
                "sub_categories": {}
            }

        if sub_id not in menu[cat_id]["sub_categories"]:
            menu[cat_id]["sub_categories"][sub_id] = {
                "id": sub_id,
                "name": r["sub_name"],
                "items": []
            }

        if r["item_id"]:
            item_data = {
                "id": r["item_id"],
                "name": r["item_name"],
                "price": r["price"],
                "is_veg": r["is_veg"],
                "contains_dairy": r["contains_dairy"],
                "contains_nuts": r["contains_nuts"],
                "is_gluten_free": r["is_gluten_free"],

                # ✅ ADDONS (THIS IS THE ONLY ADDITION)
                "addons": fetch_addons_for_item(r["item_id"])
            }

            menu[cat_id]["sub_categories"][sub_id]["items"].append(item_data)

    conn.close()
    return jsonify(menu)
@app.route("/add-order", methods=["POST"])
def add_order():
    table_no = request.form.get("table_no")
    item_name = request.form.get("item_name")
    quantity = int(request.form.get("quantity"))
    price = int(request.form.get("price"))

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO orders (table_no, item_name, quantity, price, status) VALUES (?, ?, ?, ?, ?)",
        (table_no, item_name, quantity, price, "Ordered")
    )
    con.commit()
    con.close()

    return redirect(url_for("menu_page", table=table_no))
# Place Order

@app.route("/orders")
def view_orders():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM orders
    WHERE LOWER(status) != 'served'
""")
    orders = cur.fetchall()

    conn.close()

    return render_template("orders.html", orders=orders)


# Kitchen Load
@app.route("/kitchen-load")
@admin_required
def kitchen_load():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE status IN('Ordered','Accepted','Pending')")
    count = cur.fetchone()[0]
    con.close()

    if count > 5:
        return jsonify({"load": "High", "time": "30 mins"})
    else:
        return jsonify({"load": "Normal", "time": "15 mins"})



@app.route("/update-status", methods=["POST"])
def update_status():
    order_id = request.form.get("order_id")
    new_status = request.form.get("status")

    ALLOWED_STATUS = [
        "Accepted",
        "Preparing",
        "Ready",
        "Served",
        "Cancelled"
    ]

    if new_status not in ALLOWED_STATUS:
        return jsonify({"success": False, "error": "Invalid status"})

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (new_status, order_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})
@app.route('/my-orders/<int:table_no>')
def customer_orders(table_no):

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, table_no, item_name, quantity, price, status
        FROM orders
        WHERE table_no = ?
        ORDER BY id DESC
    """, (table_no,))

    orders = cur.fetchall()

    # ✅ ADD THIS PART
    subtotal = sum(o["quantity"] * o["price"] for o in orders)
    gst = round(subtotal * 0.05, 2)
    service_charge = round(subtotal * 0.05, 2)
    grand_total = round(subtotal + gst + service_charge, 2)

    conn.close()

    return render_template(
        'customer_status.html',
        orders=orders,
        table_no=table_no,
        subtotal=subtotal,
        gst=gst,
        service_charge=service_charge,
        grand_total=grand_total
    )
@app.route('/api/customer_status')
def api_customer_status():
    table_no = request.args.get('table')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, table_no, item_name, quantity, price, status
        FROM orders
        WHERE table_no = ?
        AND status NOT IN ('PAID')
    """, (table_no,))

    orders = [dict(row) for row in cur.fetchall()]
    conn.close()

    return jsonify(orders)


# @app.route('/bill/<int:table_no>')
# def bill(table_no):
#     conn = sqlite3.connect('database.db')
#     cur = conn.cursor()

#     cur.execute("""
#         SELECT item_name, quantity, price, status
#         FROM orders
#         WHERE table_no = ?
#         AND status != 'cancelled'
#     """, (table_no,))

#     orders = cur.fetchall()

#     total = sum(order[1] * order[2] for order in orders)

#     conn.close()

#     return render_template(
#         'bill.html',
#         orders=orders,
#         table_no=table_no,
#         total=total
#     )


@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # 1️⃣ Total Orders (from orders table)
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0] or 0

    # 2️⃣ Revenue from paid bills
    cur.execute("SELECT SUM(grand_total) FROM paid_bills")
    paid_revenue = cur.fetchone()[0]

    # If no paid bills yet, show 0
    if paid_revenue is None:
        total_revenue = 0
    else:
        total_revenue = paid_revenue

    # Today revenue
    cur.execute("""
    SELECT COALESCE(SUM(grand_total),0)
    FROM paid_bills
    WHERE date(paid_at) = date('now','localtime')
    """)
    today_revenue = cur.fetchone()[0] 

# Month revenue
    cur.execute("""
    SELECT COALESCE(SUM(grand_total),0)
    FROM paid_bills
    WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m','now','localtime')
    """)
    monthly_revenue = cur.fetchone()[0] 
    # 5️⃣ Order Status Overview (KEEP SAME FORMAT)
    cur.execute("""
        SELECT status, COUNT(*)
        FROM orders
        GROUP BY status
    """)
    status_data = cur.fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        total_orders=total_orders,
        total_revenue=total_revenue,
        today_revenue=today_revenue,
        monthly_revenue=monthly_revenue,
        status_data=json.dumps(status_data)   # keep json.dumps
    )

@app.route("/menu")
@customer_required
def menu():
    print("SESSION:", session)
    table_no = request.args.get("table")
    

    # ✅ Store table number in session if provided
    if table_no:
        session["table_no"] = table_no

    # Optional safety check 
    if "table_no" not in session:
        return "Table number missing. Please scan QR again."

    print("Current Table:", session["table_no"])

    filter_type = request.args.get("filter", "all")

    query = "SELECT * FROM menu_items WHERE available = 1"

    if filter_type == "veg":
        query += " WHERE is_veg = 1"
    elif filter_type == "gluten":
        query += " WHERE is_gluten_free = 1"

    cursor.execute(query)
    items = cursor.fetchall()

    return render_template(
        "menu.html",
        items=items,
        table_no=session["table_no"]
    )
@app.route("/cart")
@customer_required
def cart():
    table_no = session.get("table_no")

    cursor.execute("""
        SELECT c.id, m.name, c.quantity, c.price
        FROM cart c
        JOIN menu_items m ON c.item_id = m.id
        WHERE c.table_no = ?
    """, (table_no,))

    items = cursor.fetchall()

    total = sum(item[2] * item[3] for item in items)

    return render_template("cart.html", items=items, total=total)

@app.route("/my_orders")
def my_orders():
    return render_template("my_orders.html")


@app.route("/kitchen")
def kitchen_orders():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
    SELECT id, table_no, item_name, quantity, price, status
    FROM orders
    WHERE status NOT IN ('Cancelled', 'Served')
    ORDER BY id ASC
""")
    orders = cur.fetchall()
    conn.close()
    return render_template("orders.html", orders=orders)

@app.route("/place_order", methods=["POST"])
def place_order():
    
    data = request.json

    table_no = session.get("table_no")
    items = data.get("items")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    for item in items:

        item_name = item["name"]

        # ✅ add addons text
        if "addons" in item and item["addons"]:
            item_name += " (" + ", ".join(item["addons"]) + ")"

        cur.execute("""
            INSERT INTO orders (table_no, item_name, quantity, price, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            table_no,
            item_name,
            item["qty"],
            item["price"],
            "Ordered"
        ))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

# @app.route("/complete_payment/<int:table_no>", methods=["POST"])
# def complete_payment(table_no):
#     conn = sqlite3.connect("database.db")
#     cursor = conn.cursor()

#     # Mark all orders of this table as PAID
#     cursor.execute("""
#         UPDATE orders
#         SET status = 'PAID'
#         WHERE table_no = ?
#     """, (table_no,))

#     conn.commit()
#     conn.close()

#     return jsonify({"success": True})
    
@app.route("/thankyou")
def thankyou():
    return render_template("thankyou.html")
    
@app.route("/api/item/<int:item_id>/addons")
def get_item_addons(item_id):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id, a.name, a.price
        FROM addons a
        JOIN menu_item_addons ia ON ia.addon_id = a.id
        WHERE ia.item_id = ? AND a.is_active = 1
    """, (item_id,))

    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {"id": r[0], "name": r[1], "price": r[2]}
        for r in rows
    ])

def fetch_addons_for_item(item_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT 
            a.id,
            a.name,
            a.price
        FROM addons a
        JOIN menu_item_addons mia ON mia.addon_id = a.id
        WHERE mia.menu_item_id = ?
          AND a.is_active = 1
    """, (item_id,)).fetchall()

    addons = []
    for r in rows:
        addons.append({
            "id": r["id"],
            "name": r["name"],
            "price": r["price"]
        })

    conn.close()
    return addons

@app.route("/api/admin_stats")
def admin_stats():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # TOTAL ORDERS (paid bills)
    cur.execute("SELECT COUNT(*) FROM paid_bills")
    total_orders = cur.fetchone()[0] or 0

    # TOTAL REVENUE
    cur.execute("SELECT COALESCE(SUM(grand_total),0) FROM paid_bills")
    total_revenue = cur.fetchone()[0] or 0

    # TODAY
    cur.execute("""
        SELECT COALESCE(SUM(grand_total),0)
        FROM paid_bills
        WHERE date(paid_at)=date('now','localtime')
    """)
    today_revenue = cur.fetchone()[0] or 0

    # YESTERDAY
    cur.execute("""
        SELECT COALESCE(SUM(grand_total),0)
        FROM paid_bills
        WHERE date(paid_at)=date('now','localtime','-1 day')
    """)
    yesterday_revenue = cur.fetchone()[0] or 0

    # MONTH
    cur.execute("""
        SELECT COALESCE(SUM(grand_total),0)
        FROM paid_bills
        WHERE strftime('%Y-%m',paid_at)=strftime('%Y-%m','now','localtime')
    """)
    month_revenue = cur.fetchone()[0] or 0

    # STATUS (from orders)
    cur.execute("""
        SELECT status, COUNT(*)
        FROM orders
        WHERE status IN ('Ordered','Preparing','Ready','Served')
        GROUP BY status
    """)
    status_data = cur.fetchall()

    # HOURLY SALES (from paid_bills)
    cur.execute("""
        SELECT strftime('%H',paid_at),
               COALESCE(SUM(grand_total),0)
        FROM paid_bills
        WHERE date(paid_at)=date('now','localtime')
        GROUP BY 1
    """)
    hour = cur.fetchall()
    hour_labels = [h[0] for h in hour]
    hour_values = [h[1] for h in hour]

    # TOP ITEMS (from orders)
    cur.execute("""
        SELECT item_name, SUM(quantity)
        FROM orders
        GROUP BY item_name
        ORDER BY 2 DESC
        LIMIT 5
    """)
    top_items = cur.fetchall()

    conn.close()

    return jsonify({
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "yesterday_revenue": yesterday_revenue,
        "month_revenue": month_revenue,
        "status_data": status_data,
        "hour_labels": hour_labels,
        "hour_values": hour_values,
        "top_items": top_items
    })
import csv
from flask import send_file
import io

@app.route("/api/admin_export_csv")
def admin_export_csv():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT id, table_no, item_name, quantity, price, status, created_at FROM orders")
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Table","Item","Quantity","Price","Status","Created At"])
    writer.writerows(rows)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="cafe_report.csv")



@app.route("/bill/<int:table_no>")
def bill_customer(table_no):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT item_name, quantity, price
    FROM orders
    WHERE table_no = ?
    AND status NOT IN ('Cancelled')
""", (table_no,))

    orders = cur.fetchall()

    subtotal = sum(o[1] * o[2] for o in orders)
    gst = round(subtotal * 0.05, 2)
    service_charge = round(subtotal * 0.05, 2)
    
    grand_total = round(subtotal + gst + service_charge, 2)
    people = request.args.get("people", default=1, type=int)
    if people <= 0:
        people = 1
    per_person = round(grand_total / people, 2)

    cur.execute("SELECT bill_generated FROM bill_status WHERE table_no = ?", (table_no,)
    )
    result = cur.fetchone()

    bill_generated = result[0] if result else 0

    conn.close()

    return render_template(
    "bill_customer.html",
    table_no=table_no,
    orders=orders,
    subtotal=subtotal,
    gst=gst,
    service_charge=service_charge,
    grand_total=grand_total,
    per_person=per_person,
    bill_generated=bill_generated
)

@app.route("/generate_bill/<int:table_no>", methods=['GET','POST'])
def generate_bill(table_no):

    print("Generate bill route triggered for table:", table_no)

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO bill_status (table_no, bill_generated)
        VALUES (?,1)
        ON CONFLICT(table_no)
        DO UPDATE SET bill_generated=1
    """, (table_no,))

    conn.commit()
    conn.close()

    return redirect(url_for('bill_customer',table_no=table_no))

# @app.route("/complete_payment/<int:table_no>", methods=["POST"])
# def complete_payment(table_no):

#     conn = sqlite3.connect("database.db")
#     cur = conn.cursor()

#     cur.execute("DELETE FROM orders WHERE table_no = ?", (table_no,))
#     cur.execute("UPDATE bill_status SET bill_generated=0 WHERE table_no=?", (table_no,))

#     print("Bill status updated")

#     conn.commit()
#     conn.close()

#     return jsonify({"success": True})

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from flask import send_file
import os

@app.route("/download_bill_pdf/<int:table_no>")
def download_bill_pdf(table_no):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT item_name, quantity, price
        FROM orders
        WHERE table_no = ?
        AND status NOT IN ('Cancelled')
    """, (table_no,))

    orders = cur.fetchall()

    subtotal = sum(o[1] * o[2] for o in orders)
    gst = round(subtotal * 0.05, 2)
    service_charge = round(subtotal * 0.05, 2)
    grand_total = round(subtotal + gst + service_charge, 2)
    people = request.args.get("people", default=1, type=int)
    if people <= 0:
        people = 1
    per_person = round(grand_total / people, 2)

    conn.close()

    filename = f"bill_table_{table_no}.pdf"
    filepath = filename

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"SmartBite Cafe - Table {table_no}", styles["Title"]))
    elements.append(Spacer(1, 12))

    data = [["Item", "Qty", "Price", "Total"]]

    for o in orders:
        data.append([o[0], o[1], f"₹{o[2]}", f"₹{o[1]*o[2]}"])

    data.append(["", "", "Subtotal", f"₹{subtotal}"])
    data.append(["", "", "GST (5%)", f"₹{gst}"])
    data.append(["", "", "Service Charge", f"₹{service_charge}"])
    data.append(["", "", "Grand Total", f"₹{grand_total}"])

    elements.append(Table(data))

    doc.build(elements)

    return send_file(filepath, as_attachment=True)

@app.route("/pay/<int:table_no>")
def pay_bill(table_no):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Get current bill details
    cur.execute("SELECT subtotal, gst, service_charge, grand_total FROM bill_summary WHERE table_no = ?", (table_no,))
    bill = cur.fetchone()

    if bill:
        subtotal, gst, service_charge, grand_total = bill

        paid_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
        INSERT INTO paid_bills (table_no, subtotal, gst, service_charge, grand_total, paid_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (table_no, subtotal, gst, service_charge, grand_total, paid_at))

        conn.commit()

    conn.close()

    return "Payment Successful!"

from datetime import datetime



@app.route("/api/pay/<int:table_no>", methods=["POST"])
def pay(table_no):

    data = request.get_json()
    payment_mode = data.get("mode")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get subtotal
    cursor.execute("""
        SELECT SUM(quantity * price) 
        FROM orders 
        WHERE table_no = ?
    """, (table_no,))

    subtotal = cursor.fetchone()[0] or 0

    if subtotal == 0:
        return jsonify({"status": "error", "message": "No active orders found"}), 400

    # Calculate charges
    gst = round(subtotal * 0.18, 2)
    service_charge = round(subtotal * 0.05, 2)
    grand_total = round(subtotal + gst + service_charge, 2)

    # Generate Transaction ID
    txn_id = "TXN" + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100,999))

    # 1️⃣ Insert into paid_bills
    cursor.execute("""
        INSERT INTO paid_bills 
        (table_no, subtotal, gst, service_charge, grand_total, paid_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (table_no, subtotal, gst, service_charge, grand_total))

    paid_bill_id = cursor.lastrowid  # 🔥 IMPORTANT FIX

    # 2️⃣ Insert into payments with correct reference
    cursor.execute("""
        INSERT INTO payments 
        (paid_bill_id, table_no, amount, payment_mode, transaction_id)
        VALUES (?, ?, ?, ?, ?)
    """, (paid_bill_id, table_no, grand_total, payment_mode, txn_id))

    # 3️⃣ Delete orders after payment
    cursor.execute("""
        DELETE FROM orders 
        WHERE table_no = ?
    """, (table_no,))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "transaction_id": txn_id
    })
@app.route("/admin/paid_bills")
def admin_paid_bills():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            pb.id,
            pb.table_no,
            pb.subtotal,
            pb.gst,
            pb.service_charge,
            pb.grand_total,
            pb.paid_at,
            p.payment_mode,
            p.transaction_id
        FROM paid_bills pb
        LEFT JOIN payments p
        ON pb.id = p.paid_bill_id   -- ✅ FIXED JOIN
        ORDER BY pb.paid_at DESC
    """)

    bills = cur.fetchall()
    conn.close()

    return render_template("admin_paid_bills.html", bills=bills)

@app.route("/table/<int:table_no>")
def table_entry(table_no):
    session["table_no"] = table_no
    return redirect(url_for("menu"))

@app.route("/api/ai_recommend/<int:table_no>")
def ai_recommend(table_no):

    mood = request.args.get("mood")
    no_dairy = request.args.get("no_dairy") == "true"
    no_nuts = request.args.get("no_nuts") == "true"
    veg_only = request.args.get("veg_only") == "true"

    print("Mood:", mood)
    print("Veg:", veg_only)
    print("No Dairy:", no_dairy)
    print("No Nuts:", no_nuts)

    recommendations = recommend(
        table_no,
        mood=mood,
        no_dairy=no_dairy,
        no_nuts=no_nuts,
        veg_only=veg_only
    )

    return jsonify(recommendations)

@app.route("/get_menu_by_mood")
def get_menu_by_mood():
    mood = request.args.get("mood")

    if mood == "happy":
        cursor.execute("SELECT * FROM menu WHERE category IN ('Desserts','Coolers')")
    elif mood == "tired":
        cursor.execute("SELECT * FROM menu WHERE category IN ('Coffee','Tea')")
    elif mood == "hungry":
        cursor.execute("SELECT * FROM menu WHERE category IN ('Burgers','Sandwiches','Pasta')")
    elif mood == "light":
        cursor.execute("SELECT * FROM menu WHERE category IN ('Healthy','Snacks')")
    else:
        cursor.execute("SELECT * FROM menu")

    items = cursor.fetchall()

    result = []
    for item in items:
        result.append({
            "id": item[0],
            "name": item[1],
            "price": item[2],
            "category": item[3],
            "image": item[4]
        })

    return jsonify(result)

@app.route("/cancel-order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Only allow cancel if still Ordered
    cur.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()

    if order and order[0].lower() == "ordered":
        cur.execute("UPDATE orders SET status = 'Cancelled' WHERE id = ?", (order_id,))
        conn.commit()

    conn.close()

    return jsonify({"success": True})

@app.route("/update-order/<int:order_id>", methods=["POST"])
def update_order(order_id):

    data = request.json
    change = data.get("quantity")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT quantity, status FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()

    if order and order[1].lower() == "ordered":
        new_qty = order[0] + change

        if new_qty > 0:
            cur.execute("UPDATE orders SET quantity = ? WHERE id = ?", (new_qty, order_id))
        else:
            cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))

        conn.commit()

    conn.close()
    return jsonify({"success": True})

@app.route("/admin/menu")
def admin_menu():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # 🔥 IMPORTANT
    cur = conn.cursor()

    # Get all menu items with subcategory name
    cur.execute("""
        SELECT m.id,
               m.name,
               m.price,
               m.image,
               m.available,
               m.is_veg AS is_veg,
               sc.name AS sub_category
        FROM menu_items m
        LEFT JOIN sub_categories sc
        ON m.sub_category_id = sc.id
    """)
    items = cur.fetchall()

    # Get subcategories for dropdown
    cur.execute("SELECT id, name FROM sub_categories")
    sub_categories = cur.fetchall()

    conn.close()

    return render_template(
        "admin_menu.html",
        items=items,
        sub_categories=sub_categories
    )
@app.route("/admin/toggle_item/<int:item_id>")
def toggle_item(item_id):

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Get current status
    cur.execute("SELECT available FROM menu_items WHERE id = ?", (item_id,))
    current = cur.fetchone()

    if current:
        new_status = 0 if current[0] == 1 else 1
        cur.execute("UPDATE menu_items SET available = ? WHERE id = ?", (new_status, item_id))

    conn.commit()
    conn.close()

    return redirect("/admin/menu")

@app.route("/admin/add_item", methods=["POST"])
def add_item():

    name = request.form.get("name")
    price = int(request.form.get("price"))
    is_veg = int(request.form.get("is_veg"))
    sub_category_id = request.form.get("sub_category_id")

    if not sub_category_id:
        return "Please select a subcategory"

    import os
    from werkzeug.utils import secure_filename
    image_file = request.files.get("image")
    # Default image first
    image_name = "default.jpg"
    if image_file and image_file.filename:
        image_name = secure_filename(image_file.filename)
        upload_folder = os.path.join(app.root_path, "static", "images", "menu")
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

    image_file.save(os.path.join(upload_folder, image_name))
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO menu_items
    (sub_category_id, name, price, is_veg, image, available)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
    sub_category_id,
    name,
    price,
    is_veg,
    image_name,
    1
    ))
    conn.commit()
    conn.close()
    return redirect("/admin/menu")
    
    

@app.route("/admin/delete_item/<int:item_id>")
def delete_item(item_id):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect("/admin/menu")

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route("/check_table")
def check_table():
    return {"table": session.get("table_no")}

    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True , use_reloader=False)