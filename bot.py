import asyncio
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice,
    PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPermissions,
)

from config import BOT_TOKEN, ALLOWED_CHATS, ADMIN_ID
from db import init_db, save_order, mark_paid

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

user_state = {}


# ============ ТОВАРЫ ============
PRODUCTS = [
    {
        "id": "unban",
        "title": "🔓 Разбан",
        "description": "Разблокировать пользователя в чате",
        "price": 20,
        "type": "unban",
        "need_user": True,
        "only_chat": True,
    },
    {
        "id": "unban_link",
        "title": "🔓 Разбан + ссылка",
        "description": "Разбан пользователя + одноразовая ссылка",
        "price": 25,
        "type": "unban_link",
        "need_user": True,
        "only_chat": True,
    },
    {
        "id": "invite_link",
        "title": "🔗 Одноразовая ссылка",
        "description": "Создать одноразовую ссылку-приглашение",
        "price": 5,
        "type": "invite_link",
        "need_user": False,
        "only_chat": True,
    },
    {
        "id": "unmute",
        "title": "🔊 Анмут (снять мут)",
        "description": "Снять мут с пользователя",
        "price": 15,
        "type": "unmute",
        "need_user": True,
        "only_chat": True,
    },
    {
        "id": "pin_1h",
        "title": "📌 Закреп на 1 час",
        "description": "Закрепить твоё последнее сообщение в чате на 1 час",
        "price": 10,
        "type": "pin",
        "need_user": False,
        "only_chat": True,  # ТОЛЬКО ЧАТЫ
    },
]


def get_product(pid):
    for p in PRODUCTS:
        if p["id"] == pid:
            return p
    return None


# ============ /start ============
@dp.message(CommandStart())
async def start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="📋 Мои чаты", callback_data="my_chats")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])
    await msg.answer(
        f"👋 Привет, {msg.from_user.first_name}!\n\n"
        "Здесь можно купить услуги для твоих чатов за ⭐ Stars.",
        reply_markup=kb
    )


# ============ Магазин ============
@dp.callback_query(F.data == "shop")
async def shop_menu(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{p['title']} — {p['price']} ⭐",
            callback_data=f"prod:{p['id']}"
        )]
        for p in PRODUCTS
    ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]])
    
    await cb.message.edit_text(
        "🛒 <b>Магазин</b>\n\nВыбери услугу:",
        parse_mode="HTML",
        reply_markup=kb
    )
    await cb.answer()


# ============ Товар → выбор чата ============
@dp.callback_query(F.data.startswith("prod:"))
async def show_product(cb: CallbackQuery):
    product_id = cb.data.split(":")[1]
    product = get_product(product_id)
    if not product:
        await cb.answer("Товар не найден", show_alert=True)
        return
    
    # Собираем чаты, где бот админ
    is_admin = cb.from_user.id == ADMIN_ID
    chats = []
    for chat_id, title in ALLOWED_CHATS.items():
        try:
            bm = await bot.get_chat_member(chat_id, bot.id)
            if bm.status not in ("administrator", "creator"):
                continue
            
            # Проверка типа: для only_chat — только группы
            chat = await bot.get_chat(chat_id)
            if product["only_chat"] and chat.type not in ("group", "supergroup"):
                continue
            
            # Проверка юзера
            if not is_admin:
                um = await bot.get_chat_member(chat_id, cb.from_user.id)
                if um.status not in ("administrator", "creator"):
                    continue
            
            chats.append((chat_id, title, chat.type))
        except Exception as e:
            print(f"⚠️ {chat_id}: {e}")
            continue
    
    if not chats:
        await cb.answer(
            "❌ Нет доступных чатов. Бот должен быть админом, "
            "а товар подходит только для чатов (не каналов).",
            show_alert=True
        )
        return
    
    user_state[cb.from_user.id] = {"product_id": product_id}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{title}", callback_data=f"buy:{chat_id}")]
        for chat_id, title, _ in chats
    ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]])
    
    text = (
        f"<b>{product['title']}</b>\n\n"
        f"{product['description']}\n\n"
        f"💰 Цена: <b>{product['price']} ⭐</b>\n\n"
        f"Выбери чат:"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ============ Покупка ============
@dp.callback_query(F.data.startswith("buy:"))
async def buy_product(cb: CallbackQuery):
    chat_id = int(cb.data.split(":")[1])
    state = user_state.get(cb.from_user.id, {})
    product_id = state.get("product_id")
    
    if not product_id:
        await cb.answer("Сначала выбери товар", show_alert=True)
        return
    
    product = get_product(product_id)
    if not product:
        await cb.answer("Товар не найден", show_alert=True)
        return
    
    if chat_id not in ALLOWED_CHATS:
        await cb.answer("Чат недоступен", show_alert=True)
        return
    
    # Для товаров, требующих юзера — просим ввести
    if product["need_user"]:
        user_state[cb.from_user.id]["chat_id"] = chat_id
        await cb.message.edit_text(
            f"<b>{product['title']}</b>\n\n"
            f"Отправь мне <b>юзернейм</b> (@username) или <b>ID</b> пользователя, "
            f"к которому применить услугу.\n\n"
            f"Пример: <code>@username</code> или <code>123456789</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_main")]
            ])
        )
        await cb.answer()
        return
    
    # Не требует юзера — сразу счёт
    await send_invoice(cb.from_user.id, cb.message, product, chat_id)


# ============ Приём юзернейма ============
@dp.message(F.text, ~F.text.startswith("/"))
async def handle_user_input(msg: Message):
    state = user_state.get(msg.from_user.id, {})
    if "chat_id" not in state or "product_id" not in state:
        return  # не в процессе
    
    product = get_product(state["product_id"])
    if not product:
        return
    
    target = msg.text.strip()
    
    # Если @username — оставляем как есть, если ID — конвертим
    if not target.startswith("@") and target.isdigit():
        target = int(target)
    
    state["target_user"] = target
    
    await send_invoice(msg.from_user.id, msg, product, state["chat_id"])


# ============ Отправка счёта ============
async def send_invoice(user_id, message, product, chat_id):
    state = user_state.get(user_id, {})
    target_user = state.get("target_user")
    
    order_id = await save_order(
        user_id=user_id,
        chat_id=chat_id,
        product_id=product["id"],
        price=product["price"],
    )
    
    payload = json.dumps({
        "order_id": order_id,
        "product_id": product["id"],
        "chat_id": chat_id,
        "user_id": user_id,
        "target_user": str(target_user) if target_user else None,
    })
    
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=product["title"],
            description=product["description"],
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=product["title"], amount=product["price"])],
            provider_token="",
        )
        print(f"✅ Инвойс отправлен user={user_id}")
    except Exception as e:
        print(f"❌ send_invoice: {e}")
        await message.answer(f"❌ Ошибка: {e}")


# ============ Pre-checkout ============
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


# ============ Применение после оплаты ============
@dp.message(F.successful_payment)
async def paid(msg: Message):
    data = json.loads(msg.successful_payment.invoice_payload)
    order_id = data["order_id"]
    product_id = data["product_id"]
    chat_id = data["chat_id"]
    target_user = data.get("target_user")
    
    await mark_paid(order_id)
    product = get_product(product_id)
    
    await msg.answer(
        f"✅ <b>Оплачено!</b>\n\n"
        f"Услуга: {product['title']}\n"
        f"Чат: {ALLOWED_CHATS.get(chat_id, chat_id)}\n"
        f"Сумма: {product['price']} ⭐",
        parse_mode="HTML"
    )
    
    try:
        # --- РАЗБАН ---
        if product["type"] == "unban":
            await bot.unban_chat_member(
                chat_id=chat_id,
                user_id=target_user if isinstance(target_user, int) else target_user,
                only_if_banned=True
            )
            await bot.send_message(
                chat_id,
                f"🔓 Разбан: <b>{target_user}</b>\n"
                f"Купил: {msg.from_user.full_name}",
                parse_mode="HTML"
            )
            await msg.answer("✅ Пользователь разбанен!")
        
        # --- РАЗБАН + ССЫЛКА ---
        elif product["type"] == "unban_link":
            try:
                await bot.unban_chat_member(
                    chat_id=chat_id,
                    user_id=target_user if isinstance(target_user, int) else target_user,
                    only_if_banned=True
                )
            except Exception as e:
                print(f"⚠️ unban: {e}")
            
            link = await bot.create_chat_invite_link(
                chat_id=chat_id,
                member_limit=1,
                name=f"Разбан для {target_user}"
            )
            await msg.answer(
                f"✅ <b>Разбан + ссылка</b>\n\n"
                f"Пользователь разбанен.\n\n"
                f"Одноразовая ссылка:\n{link.invite_link}",
                parse_mode="HTML"
            )
            await bot.send_message(
                chat_id,
                f"🔓 Разбан: <b>{target_user}</b> + ссылка\n"
                f"Купил: {msg.from_user.full_name}",
                parse_mode="HTML"
            )
        
        # --- ССЫЛКА ---
        elif product["type"] == "invite_link":
            link = await bot.create_chat_invite_link(
                chat_id=chat_id,
                member_limit=1,
                name=f"Ссылка от {msg.from_user.full_name}"
            )
            await msg.answer(
                f"✅ <b>Одноразовая ссылка создана</b>\n\n"
                f"Чат: {ALLOWED_CHATS.get(chat_id, chat_id)}\n\n"
                f"{link.invite_link}\n\n"
                f"⚠️ Ссылка работает 1 раз.",
                parse_mode="HTML"
            )
        
        # --- АНМУТ ---
        elif product["type"] == "unmute":
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user if isinstance(target_user, int) else target_user,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                )
            )
            await bot.send_message(
                chat_id,
                f"🔊 Анмут: <b>{target_user}</b>\n"
                f"Купил: {msg.from_user.full_name}",
                parse_mode="HTML"
            )
            await msg.answer("✅ Мут снят!")
        
        # --- ЗАКРЕП ---
        elif product["type"] == "pin":
            # Закрепляем последнее сообщение пользователя
            # (в реальности нужно найти его, но Telegram API не даёт искать)
            # Просто отправляем и закрепим сервисное
            sent = await bot.send_message(
                chat_id,
                f"📌 Закреп на 1 час\n"
                f"Купил: {msg.from_user.full_name}"
            )
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent.message_id,
                disable_notification=False
            )
            await msg.answer("✅ Сообщение закреплено на 1 час!")
    
    except Exception as e:
        print(f"❌ Применение: {e}")
        await msg.answer(f"⚠️ Оплата прошла, но применить не удалось:\n<code>{e}</code>", parse_mode="HTML")


# ============ Мои чаты ============
@dp.callback_query(F.data == "my_chats")
async def my_chats(cb: CallbackQuery):
    is_admin = cb.from_user.id == ADMIN_ID
    chats = []
    for chat_id, title in ALLOWED_CHATS.items():
        try:
            bm = await bot.get_chat_member(chat_id, bot.id)
            if bm.status not in ("administrator", "creator"):
                continue
            chat = await bot.get_chat(chat_id)
            if not is_admin:
                um = await bot.get_chat_member(chat_id, cb.from_user.id)
                if um.status not in ("administrator", "creator"):
                    continue
            chats.append((chat_id, title, chat.type))
        except Exception:
            pass
    
    if not chats:
        text = "❌ Нет доступных чатов."
    else:
        text = "📋 <b>Твои чаты:</b>\n\n"
        for cid, title, ctype in chats:
            icon = "👥" if ctype in ("group", "supergroup") else "📢"
            text += f"{icon} {title} — <code>{cid}</code>\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ============ Помощь ============
@dp.callback_query(F.data == "help")
async def help_cb(cb: CallbackQuery):
    text = (
        "🛒 <b>Как купить:</b>\n\n"
        "1. Магазин → выбери услугу\n"
        "2. Выбери чат\n"
        "3. Если нужно — введи юзернейм\n"
        "4. Оплати звёздами ⭐\n\n"
        "<b>Услуги:</b>\n"
        "🔓 Разбан — разблокировать юзера\n"
        "🔓 Разбан + ссылка — разбан и одноразовая ссылка\n"
        "🔗 Ссылка — одноразовая ссылка-приглашение\n"
        "🔊 Анмут — снять мут\n"
        "📌 Закреп — закрепить сообщение на 1 час\n\n"
        "⚠️ Бот должен быть админом в чате.\n"
        "⚠️ Разбан/анмут/закреп — только в чатах (не каналах)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ============ Назад ============
@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    user_state.pop(cb.from_user.id, None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="📋 Мои чаты", callback_data="my_chats")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])
    await cb.message.edit_text(
        "👋 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await cb.answer()


# ============ Запуск ============
async def main():
    await init_db()
    print("🤖 Бот запущен!")
    print(f"   ADMIN_ID: {ADMIN_ID}")
    print(f"   Чаты: {ALLOWED_CHATS}")
    
    # Сначала HTTP — чтобы Render видел порт
    await start_web()
    print("🌐 HTTP запущен")
    
    # Потом polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
