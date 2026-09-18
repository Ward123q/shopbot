import aiosqlite
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, chat_id INTEGER,
            product_id TEXT, price INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()

async def save_order(user_id, chat_id, product_id, price, status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, chat_id, product_id, price, status) VALUES (?,?,?,?,?)",
            (user_id, chat_id, product_id, price, status)
        )
        await db.commit()
        return cur.lastrowid

async def mark_paid(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
        await db.commit()