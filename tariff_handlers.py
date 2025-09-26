# tariff_handlers.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from keyboards import tariffs_kb, client_main_kb, client_kb, empty_kb
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from helpers import send_temp, send_ephemeral
from reg import profile_open
from reg import db as reg_db  # импорт клиента БД (вверху файла)
router = Router()

INVISIBLE = "\u2063"  # невидимый, но НЕ пустой символ

async def show_with_reply_kb(message: Message, text: str, kb: ReplyKeyboardMarkup, *, md: bool = True):
    if md:
        await send_temp(message, text, parse_mode="Markdown", reply_markup=kb)
    else:
        await send_temp(message, text, reply_markup=kb)


# ---------- временное состояние ----------
class TempState:
    TARIFF = "temp_tariff"

# ---------- локальные reply-клавиатуры этого модуля ----------
def base_tariff_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Купить")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False,
    )



def value_tariff_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Чат с куратором"), KeyboardButton(text="Тренировки")],
            [KeyboardButton(text="💳 Купить")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False,
    )
# tariff_handlers.py (рядом с другими KB)
def tariff_status_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Изменить")],
            [KeyboardButton(text="🏠 На главную")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=False,
    )

def buy_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Купить")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False,
    )

def section_action_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Купить")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False,
    )

def value_tariff_final_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Чат с куратором"), KeyboardButton(text="Тренировки")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False,
    )



@router.message(StateFilter("*"), F.text.in_({"Меню", "Профиль", "Тариф"}))
async def forced_exit_from_fsm(message: Message, state: FSMContext):
    await state.clear()
    if message.text == "Профиль":
        await profile_open(message)
    elif message.text == "Тариф":
        await show_tariffs(message, state)
    else:
        u = await reg_db.user.find_unique(where={"tg_id": message.from_user.id})
        has_app = bool(u and u.tariffName)
        await show_with_reply_kb(message, "🏠 Главное меню клиента", client_kb(has_app), md=False)


# ---------- список тарифов ----------
@router.message(StateFilter(None), F.text == "Тариф")
async def show_tariffs(message: Message, state: FSMContext):
    await state.clear()
    u = await reg_db.user.find_unique(where={"tg_id": message.from_user.id})
    if u and u.tariffName:
        await show_with_reply_kb(
            message,
            f"У вас куплен тариф: *{u.tariffName}*",
            tariff_status_kb()
        )
        return
    await show_with_reply_kb(message, "Выберите подходящий тариф:", tariffs_kb())

@router.message(StateFilter(None), F.text == "✏️ Изменить")
async def tariff_change(message: Message, state: FSMContext):
    await state.clear()
    await show_with_reply_kb(message, "Выберите новый тариф:", tariffs_kb())

@router.message(StateFilter(None), F.text == "🏠 На главную")
async def tariff_to_home(message: Message, state: FSMContext):
    await state.clear()
    u = await reg_db.user.find_unique(where={"tg_id": message.from_user.id})
    has_app = bool(u and u.tariffName)
    await show_with_reply_kb(message, "🏠 Главное меню клиента", client_kb(has_app), md=False)



# ---------- Базовый ----------
@router.message(StateFilter(None), F.text == "💼 Базовый")
async def show_base_tariff(message: Message, state: FSMContext):
    await state.set_data({TempState.TARIFF: "Базовый"})
    await show_with_reply_kb(
        message,
        "🧾 *Базовый тариф*\n\nТут будет ваше описание.",
        base_tariff_menu_kb()
    )

# ---------- Выгодный ----------
@router.message(StateFilter(None), F.text == "🤑 Выгодный")
async def show_value_tariff(message: Message, state: FSMContext):
    await state.set_data({TempState.TARIFF: "Выгодный"})
    await show_with_reply_kb(
        message,
        "🧾 *Выгодный тариф*\n\nЗдесь будет описание тарифа.",
        buy_kb()
    )

# ---------- Максимум ----------
@router.message(StateFilter(None), F.text == "💎 Максимум")
async def show_maximum_tariff(message: Message, state: FSMContext):
    await state.set_data({TempState.TARIFF: "Максимум"})
    await show_with_reply_kb(
        message,
        "🧾 *Максимум*\n\nЗдесь будет описание тарифа.",
        buy_kb()
    )

@router.message(StateFilter(None), F.text == "💳 Купить")
async def handle_tariff_purchase(message: Message, state: FSMContext):
    data = await state.get_data()
    bought_tariff = data.get(TempState.TARIFF, "Базовый")

    await reg_db.user.upsert(
        where={"tg_id": message.from_user.id},
        data={
            "create": {
                "tg_id": message.from_user.id,
                "username": message.from_user.username,
                "tariffName": bought_tariff,
            },
            "update": {
                "username": message.from_user.username,
                "tariffName": bought_tariff,
            },
        },
    )

    await send_temp(message, f"✅ Поздравляем! Вы оформили тариф *{bought_tariff}*", parse_mode="Markdown")

    u = await reg_db.user.find_unique(where={"tg_id": message.from_user.id})
    has_app = bool(u and u.tariffName)
    await show_with_reply_kb(message, "🏠 Главное меню клиента", client_kb(has_app), md=False)
    await state.clear()




# ---------- Назад (в клиентское меню) ----------
@router.message(StateFilter(None), F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    u = await reg_db.user.find_unique(where={"tg_id": message.from_user.id})
    has_app = bool(u and u.tariffName)
    await show_with_reply_kb(message, "🏠 Главное меню клиента", client_kb(has_app), md=False)

