# database.py
import sqlite3
from config import DB_NAME


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            info TEXT DEFAULT '',
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # standart sozlamalar
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                ("admin_username", "@your_admin"))
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                ("channel_url", "https://t.me/your_channel"))
    conn.commit()
    conn.close()


# ---------- SETTINGS ----------
def get_setting(key: str) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()


# ---------- CATEGORIES ----------
def add_category(name: str) -> int:
    conn = get_conn()
    cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_categories():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    return rows


def get_category(category_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    conn.close()
    return row


def delete_category(category_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM items WHERE category_id = ?", (category_id,))
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()


def rename_category(category_id: int, new_name: str):
    conn = get_conn()
    conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id))
    conn.commit()
    conn.close()


# ---------- ITEMS ----------
def add_item(category_id: int, name: str, price: int, info: str = "") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO items (category_id, name, price, info) VALUES (?, ?, ?, ?)",
        (category_id, name, price, info)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_items_by_category(category_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM items WHERE category_id = ? ORDER BY id", (category_id,)
    ).fetchall()
    conn.close()
    return rows


def get_item(item_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return row


def update_item_price(item_id: int, new_price: int):
    conn = get_conn()
    conn.execute("UPDATE items SET price = ? WHERE id = ?", (new_price, item_id))
    conn.commit()
    conn.close()


def update_item_info(item_id: int, new_info: str):
    conn = get_conn()
    conn.execute("UPDATE items SET info = ? WHERE id = ?", (new_info, item_id))
    conn.commit()
    conn.close()


def update_item_name(item_id: int, new_name: str):
    conn = get_conn()
    conn.execute("UPDATE items SET name = ? WHERE id = ?", (new_name, item_id))
    conn.commit()
    conn.close()


def delete_item(item_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
