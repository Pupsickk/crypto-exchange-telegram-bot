import os
from dotenv import load_dotenv
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
)
import sqlite3
from datetime import datetime
import asyncio

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
if not BOT_TOKEN or not ADMIN_ID.isdigit():
    raise RuntimeError("Set BOT_TOKEN and numeric ADMIN_ID in .env before starting the bot.")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM состояния
class ExchangeStates(StatesGroup):
    select_currency = State()
    enter_amount = State()
    enter_wallet = State()
    confirm_order = State()
    admin_comment = State()
    proof_upload = State()  # новое состояние для скрина
    # калькулятор
    calculator_select_pair = State()
    calculator_enter_amount = State()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('exchange_bot.db')
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS exchange_rates")
    cursor.execute('''
    CREATE TABLE exchange_rates (
        currency_pair TEXT PRIMARY KEY,
        rate REAL,
        min_amount REAL,
        max_amount REAL,
        updated_at TEXT
    )''')

    default_rates = [
        ('USDT_RUB', 90.5, 1000, 500000, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('BTC_USDT', 0.000035, 0.001, 10, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('ETH_USDT', 0.00055, 0.01, 50, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('RUB_USDT', 0.011, 1000, 500000, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('USDT_BTC', 28571, 50, 50000, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('USDT_ETH', 1818.18, 20, 20000, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ]
    cursor.executemany('''
    INSERT INTO exchange_rates (currency_pair, rate, min_amount, max_amount, updated_at)
    VALUES (?, ?, ?, ?, ?)
    ''', default_rates)

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exchange_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        from_currency TEXT,
        to_currency TEXT,
        amount REAL,
        receive_amount REAL,
        wallet_address TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# Клавиатуры
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Создать обмен")],
            [KeyboardButton(text="📊 Курсы валют"), KeyboardButton(text="📋 Мои заявки")],
            [KeyboardButton(text="🧮 Калькулятор")],
            [KeyboardButton(text="📞 Поддержка")]
        ],
        resize_keyboard=True
    )

def get_currency_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="USDT → RUB", callback_data="pair_USDT_RUB")],
        [InlineKeyboardButton(text="BTC → USDT", callback_data="pair_BTC_USDT")],
        [InlineKeyboardButton(text="ETH → USDT", callback_data="pair_ETH_USDT")],
        [InlineKeyboardButton(text="RUB → USDT", callback_data="pair_RUB_USDT")],
        [InlineKeyboardButton(text="USDT → BTC", callback_data="pair_USDT_BTC")],
        [InlineKeyboardButton(text="USDT → ETH", callback_data="pair_USDT_ETH")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def get_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def get_admin_order_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{order_id}")]
    ])

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "💱 Добро пожаловать!\n\nОбменяйте валюту по выгодному курсу.",
        reply_markup=get_main_menu()
    )

# Показ курсов
@dp.message(F.text == "📊 Курсы валют")
async def show_rates(message: types.Message):
    conn = sqlite3.connect('exchange_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exchange_rates")
    rates = cursor.fetchall()
    conn.close()

    text = "📊 Текущие курсы обмена:\n\n"
    for r in rates:
        pair = r[0].replace("_", " → ")
        text += f"{pair}\nКурс: 1 {r[0].split('_')[0]} = {r[1]} {r[0].split('_')[1]}\nЛимиты: {r[2]} - {r[3]}\n\n"
    await message.answer(text)

# Создать обмен
@dp.message(F.text == "🔄 Создать обмен")
async def start_exchange(message: types.Message, state: FSMContext):
    await message.answer("Выберите направление:", reply_markup=get_currency_keyboard())
    await state.set_state(ExchangeStates.select_currency)

# Выбор пары
@dp.callback_query(F.data.startswith("pair_"), ExchangeStates.select_currency)
async def select_currency_pair(callback: CallbackQuery, state: FSMContext):
    currency_pair = "_".join(callback.data.split("_")[1:])
    conn = sqlite3.connect('exchange_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT rate,min_amount,max_amount FROM exchange_rates WHERE currency_pair=?",(currency_pair,))
    info = cursor.fetchone()
    conn.close()
    if not info:
        await callback.message.answer("❌ Ошибка: курс не найден")
        await state.clear()
        return

    rate, mi, ma = info
    await state.update_data(currency_pair=currency_pair)
    await callback.message.answer(
        f"{currency_pair.replace('_',' → ')}\nКурс: 1 {currency_pair.split('_')[0]} = {rate} {currency_pair.split('_')[1]}\n"
        f"Минимум: {mi}, максимум: {ma}\nВведите сумму для обмена:"
    )
    await state.set_state(ExchangeStates.enter_amount)
    await callback.answer()

# Ввод суммы
@dp.message(ExchangeStates.enter_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.replace(",", "."))
        data = await state.get_data()
        cp = data['currency_pair']
        conn = sqlite3.connect('exchange_bot.db')
        c = conn.cursor()
        c.execute("SELECT rate,min_amount,max_amount FROM exchange_rates WHERE currency_pair=?",(cp,))
        rate, mi, ma = c.fetchone()
        conn.close()
        if amt<mi:
            await message.answer(f"Минимум {mi}")
            return
        if amt>ma:
            await message.answer(f"Максимум {ma}")
            return
        recv = round(amt*rate,8)
        await state.update_data(amount=amt, receive_amount=recv)
        await message.answer(f"Введите адрес кошелька для {cp.split('_')[1]}:")
        await state.set_state(ExchangeStates.enter_wallet)
    except:
        await message.answer("Введите число")

# Ввод кошелька
@dp.message(ExchangeStates.enter_wallet)
async def process_wallet(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    await state.update_data(wallet=wallet)
    d = await state.get_data()
    cp = d['currency_pair']
    await message.answer(
        f"Направление: {cp.replace('_',' → ')}\nСумма: {d['amount']} -> {d['receive_amount']}\nКошелек: {wallet}\nПодтвердите:",
        reply_markup=get_confirm_keyboard()
    )
    await state.set_state(ExchangeStates.confirm_order)

# Подтверждение
@dp.callback_query(F.data=="confirm", ExchangeStates.confirm_order)
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    user_id = callback.from_user.id
    username = callback.from_user.username or str(user_id)
    cp = d['currency_pair']
    amount = d['amount']
    recv = d['receive_amount']
    wallet = d['wallet']
    from_curr = cp.split('_')[0]
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pay = {"USDT":"TRC20: Txxxxxxxx","BTC":"1A1z...","ETH":"0x71C...","RUB":"Сбербанк 4276****1234"}.get(from_curr,"Реквизиты позже")

    conn = sqlite3.connect('exchange_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO exchange_orders(user_id,username,from_currency,to_currency,amount,receive_amount,wallet_address,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (user_id,username,cp.split('_')[0],cp.split('_')[1],amount,recv,wallet,created))
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    await callback.message.answer(
        f"✅ Заявка #{order_id} создана.\nОтправьте {amount} {from_curr} на:\n{pay}\n\n"
        f"После перевода отправьте сюда скриншот/квитанцию.",
        reply_markup=None
    )
    await state.update_data(order_id=order_id)
    await state.set_state(ExchangeStates.proof_upload)
    await callback.answer()

# Получение скрина
@dp.message(ExchangeStates.proof_upload)
async def handle_payment_proof(message: types.Message, state: FSMContext):
    d = await state.get_data()
    order_id = d['order_id']

    # проверяем наличие изображения или документа
    if not message.photo and not message.document:
        await message.answer("Пожалуйста, отправьте изображение или документ с подтверждением.")
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    # Берём данные заявки из базы
    conn = sqlite3.connect('exchange_bot.db')
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, from_currency, to_currency, amount, receive_amount, wallet_address, created_at
        FROM exchange_orders WHERE id=?
    """, (order_id,))
    order = c.fetchone()
    conn.close()

    if not order:
        await message.answer("Ошибка: заявка не найдена. Обратитесь в поддержку.")
        await state.clear()
        return

    user_id, username, from_curr, to_curr, amount, recv, wallet, created = order

    # Определяем реквизиты для оплаты
    payment_details = {
        "USDT": "TRC20: Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "ETH": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
        "RUB": "Сбербанк 4276********1234"
    }.get(from_curr, "Реквизиты будут предоставлены оператором")

    # Сообщение админу
    admin_caption = (
        f"🛒 Новая заявка на обмен #{order_id}\n\n"
        f"👤 Пользователь: @{username} (ID: {user_id})\n"
        f"🔹 Направление: {from_curr} → {to_curr}\n"
        f"🔹 Сумма: {amount} → {recv}\n"
        f"🔹 Кошелек: {wallet}\n"
        f"🔹 Для оплаты: {payment_details}\n"
        f"🕒 Время: {created}"
    )

    # Отправляем админу скриншот + данные
    try:
        await bot.send_photo(
            ADMIN_ID,
            photo=file_id,
            caption=admin_caption,
            reply_markup=get_admin_order_keyboard(order_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке скриншота админу: {e}")

    # Уведомляем пользователя
    await message.answer(
        "Спасибо! Скриншот отправлен администратору. "
        "После проверки оплата будет подтверждена.",
        reply_markup=get_main_menu()
    )

    await state.clear()


# Калькулятор
@dp.message(F.text == "🧮 Калькулятор")
async def calc_start(message: types.Message, state:FSMContext):
    await message.answer("Выберите направление:", reply_markup=get_currency_keyboard())
    await state.set_state(ExchangeStates.calculator_select_pair)

@dp.callback_query(F.data.startswith("pair_"), ExchangeStates.calculator_select_pair)
async def calc_pair(callback:CallbackQuery,state:FSMContext):
    cp = "_".join(callback.data.split("_")[1:])
    conn = sqlite3.connect('exchange_bot.db')
    c = conn.cursor()
    c.execute("SELECT rate FROM exchange_rates WHERE currency_pair=?",(cp,))
    info = c.fetchone()
    conn.close()
    if not info:
        await callback.message.answer("Ошибка: курс не найден")
        await state.clear()
        return
    await state.update_data(currency_pair=cp, rate=info[0])
    await callback.message.answer(f"Введите сумму в {cp.split('_')[0]}:")
    await state.set_state(ExchangeStates.calculator_enter_amount)
    await callback.answer()

@dp.message(ExchangeStates.calculator_enter_amount)
async def calc_amount(message:types.Message,state:FSMContext):
    try:
        amt = float(message.text.replace(",","."))
        d = await state.get_data()
        recv = round(amt*d['rate'],8)
        await message.answer(f"{amt} {d['currency_pair'].split('_')[0]} -> {recv} {d['currency_pair'].split('_')[1]}")
        await state.clear()
    except:
        await message.answer("Введите число")

# Мои заявки
@dp.message(F.text=="📋 Мои заявки")
async def show_orders(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect('exchange_bot.db')
    c = conn.cursor()
    c.execute("SELECT id,from_currency,to_currency,amount,receive_amount,status,created_at FROM exchange_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10",(uid,))
    orders = c.fetchall()
    conn.close()
    if not orders:
        await message.answer("Заявок нет")
        return
    txt = "Ваши заявки:\n\n"
    for o in orders:
        st = "🟢" if o[5]=="completed" else "🟡" if o[5]=="pending" else "🔴"
        txt += f"#{o[0]} {o[1]}->{o[2]} {o[3]}->{o[4]} {st} {o[5]}\n{o[6]}\n\n"
    await message.answer(txt)

# Поддержка
@dp.message(F.text=="📞 Поддержка")
async def support(message: types.Message):
    await message.answer("Поддержка: @support_manager")

# Отмена
@dp.callback_query(F.data=="cancel")
async def cancel(callback:CallbackQuery,state:FSMContext):
    await state.clear()
    await callback.message.answer("Отменено",reply_markup=get_main_menu())
    await callback.answer()

# Админ подтверждение/отклонение (остались прежними, без изменений)
@dp.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_order(callback: CallbackQuery):
    if str(callback.from_user.id)!=ADMIN_ID:
        await callback.answer("Нет доступа")
        return
    order_id=callback.data.split("_")[2]
    conn=sqlite3.connect('exchange_bot.db');c=conn.cursor()
    c.execute("SELECT user_id,to_currency,receive_amount,wallet_address FROM exchange_orders WHERE id=?",(order_id,))
    o=c.fetchone()
    if not o: await callback.answer("Нет");return
    uid,to_curr,recv,wallet=o
    c.execute("UPDATE exchange_orders SET status='completed',updated_at=? WHERE id=?",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),order_id))
    conn.commit();conn.close()
    try:
        await bot.send_message(uid,f"✅ Заявка #{order_id} выполнена.\n{recv} {to_curr} отправлены на {wallet}")
    except: pass
    await callback.message.edit_text(f"✅ Заявка #{order_id} подтверждена.")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: CallbackQuery, state:FSMContext):
    if str(callback.from_user.id)!=ADMIN_ID:
        await callback.answer("Нет доступа");return
    order_id=callback.data.split("_")[2]
    await state.update_data(order_id=order_id)
    await callback.message.answer("Причина отказа:")
    await state.set_state(ExchangeStates.admin_comment)
    await callback.answer()

@dp.message(ExchangeStates.admin_comment)
async def admin_comment(message:types.Message,state:FSMContext):
    d=await state.get_data();order_id=d['order_id'];comment=message.text
    conn=sqlite3.connect('exchange_bot.db');c=conn.cursor()
    c.execute("SELECT user_id FROM exchange_orders WHERE id=?",(order_id,))
    uid=c.fetchone()[0]
    c.execute("UPDATE exchange_orders SET status='rejected',updated_at=? WHERE id=?",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),order_id))
    conn.commit();conn.close()
    try:
        await bot.send_message(uid,f"❌ Заявка #{order_id} отклонена.\nПричина: {comment}")
    except: pass
    await message.answer(f"Отклонена #{order_id}")
    await state.clear()

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())

