CATEGORIES = [
    {"id": "design", "title": "🎨 Оформление"},
    {"id": "moder", "title": "🛡 Модерация"},
    {"id": "broadcast", "title": "📢 Рассылки"},
]

PRODUCTS = [
    {"id": "pin_1h", "category": "design", "title": "Закреп на 1 час",
     "description": "Закрепит сообщение в чате на 1 час",
     "price": 10, "type": "pin", "duration_hours": 1},
    {"id": "pin_24h", "category": "design", "title": "Закреп на 24 часа",
     "description": "Закрепит сообщение на сутки",
     "price": 50, "type": "pin", "duration_hours": 24},
    {"id": "antispam_7d", "category": "moder", "title": "Анти-спам 7 дней",
     "description": "Удаляет спам и мат",
     "price": 150, "type": "antispam", "duration_hours": 168},
    {"id": "broadcast_1", "category": "broadcast", "title": "Рассылка 1 сообщения",
     "description": "Отправит сообщение всем подписчикам",
     "price": 100, "type": "broadcast"},
]

def get_product(pid):
    for p in PRODUCTS:
        if p["id"] == pid:
            return p
    return None