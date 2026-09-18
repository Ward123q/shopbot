import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8921029996:AAGmPpqmj7qsN115Vn3DzNbCqKZPcwtt6lc")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7823802800"))

ALLOWED_CHATS = {
    -1003018474298: "anon chat",
    -1002527332271: "анон хайфа крайот",
}

DB_PATH = "shop.db"