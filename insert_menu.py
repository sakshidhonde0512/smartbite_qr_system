import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

menu = [
    ("Veg Sandwich", 80, "Snacks", "Yes", "Gluten"),
    ("Paneer Burger", 120, "Snacks", "Yes", "Dairy"),
    ("Chicken Pizza", 250, "Main Course", "No", "Dairy"),
    ("Green Salad", 90, "Healthy", "Yes", "None"),
    ("Cold Coffee", 100, "Beverages", "Yes", "Dairy")
]

cur.executemany(
    "INSERT INTO menu_items (name, price, category, is_veg, allergens) VALUES (?, ?, ?, ?, ?)",
    menu
)

conn.commit()
conn.close()

print("Menu inserted successfully")