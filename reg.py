from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from prisma import Prisma
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helpers import send_temp, send_keep   # <- вместо from bot import ...
import re
from keyboards import client_kb, empty_kb
from aiogram.types import CallbackQuery
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-'\s]{1,29}$")

def _name_ok(v: str) -> bool:
    return bool(NAME_RE.fullmatch((v or "").strip()))

def _name_fix(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).title()

router = Router()
db = Prisma()

reg_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Зарегистрироваться")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,   # оставляем меню на экране, но без "прилипания"
)

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Бесплатная консультация"), KeyboardButton(text="📝 Регистрация")],
            [KeyboardButton(text="ℹ️ О нас")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


CLIENT_PROFILE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✏️ Изменить данные")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


class ClientFSM(StatesGroup):
    accept_offer = State()
    first_name   = State()
    last_name    = State()
    email        = State()
    phone        = State()
    height_cm    = State()
    weight_kg    = State()
    age          = State()

class EditClientFSM(StatesGroup):
    menu       = State()
    first_name = State()
    last_name  = State()
    email      = State()
    phone      = State()
    height_cm  = State()
    weight_kg  = State()
    age        = State()

# добавь это рядом с другими утилитами (после def _render_client_preview ... или сразу после импортов)

async def ask_input(message: Message, text: str, *, markdown: bool = True):
    kb = empty_kb()
    if markdown:
        await send_temp(message, text, parse_mode="Markdown", reply_markup=kb)
    else:
        await send_temp(message, text, reply_markup=kb)


def _email_ok(v: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v or "") is not None

def _phone_ok(v: str) -> bool:
    digits = re.sub(r"\D", "", v or "")
    return 10 <= len(digits) <= 12
def _cell(v: str) -> str:  # капсула
    return f"`{v}`"

def _v(v, unit: str = "") -> str:
    return "-" if v in (None, "", "-") else f"{v}{unit}"

def _render_client_preview(data: dict) -> str:
    rows = [
        (_cell("Имя:"),     _cell(_v(data.get("first_name")))),
        (_cell("Фамилия:"), _cell(_v(data.get("last_name")))),
        (_cell("E-mail:"),  _cell(_v(data.get("email")))),
        (_cell("Телефон:"), _cell(_v(data.get("phone")))),
        (_cell("Рост:"),    _cell(_v(data.get("height_cm"), " см"))),
        (_cell("Вес:"),     _cell(_v(data.get("weight_kg"), " кг"))),
        (_cell("Возраст:"), _cell(_v(data.get("age")))),
    ]
    body = "\n\n".join(f"{l}  {r}" for l, r in rows)
    return "✏️ *Заполните ваши данные:*\n\n" + body + "\n\nи нажмите Зарегистрироваться"

async def _preview_form(message: Message, state: FSMContext):
    data = await state.get_data()
    await send_temp(
        message,
        "✏️ *Заполните ваши данные ниже:*",
        parse_mode="Markdown",
        reply_markup=build_inline_profile_kb(data)
    )

# === Регистрация КЛИЕНТА ===

async def show_client_reg(message: Message, state: FSMContext):
    await state.clear()
    await send_temp(
        message,
        "❗ Для регистрации клиента заполните данные и нажмите «✅ Зарегистрироваться».",
        reply_markup=reg_kb,
    )
    await state.set_state(ClientFSM.first_name)
    await _preview_form(message, state)
    await ask_input(message, "✏️ Введите ваше *имя*:")

@router.message(lambda m: isinstance(m.text, str) and "регистрац" in m.text.lower())
async def client_entry(message: Message, state: FSMContext):
    print("DEBUG: client_entry сработал:", message.text)

    await state.clear()
    
    # Сразу запускаем регистрацию — даже если пользователь уже есть
    await state.set_state(ClientFSM.accept_offer)
    
    await send_temp(
    message,
    "📄 *Оферта*\n\n"
    "Здесь будет размещён текст пользовательского соглашения.\n"
    "Нажмите *Принять*, чтобы продолжить регистрацию.",
    reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Принять"), KeyboardButton(text="❌ Отклонить")]],
        resize_keyboard=True,
        one_time_keyboard=False,   # без is_persistent
    ),
    parse_mode="Markdown"
)

@router.message(ClientFSM.accept_offer, F.text.in_({"✅ Принять", "Принять"}))
async def accept_offer(message: Message, state: FSMContext):
    await db.user.upsert(
        where={"tg_id": message.from_user.id},
        data={
            "create": {
                "tg_id": message.from_user.id,
                "username": message.from_user.username,
                "agreed_offer": True,
            },
            "update": {
                "username": message.from_user.username,
                "agreed_offer": True,
            },
        },
    )
    await state.set_state(ClientFSM.first_name)
    await send_temp(message, "❗ Для регистрации клиента заполните данные и нажмите «✅ Зарегистрироваться».", reply_markup=reg_kb)
    await _preview_form(message, state)
    await ask_input(message, "✏️ Введите ваше *имя*:")



# reg.py — хендлер отклонения оферты
@router.message(ClientFSM.accept_offer, F.text.in_({"❌ Отклонить", "Отклонить"}))
async def decline_offer(message: Message, state: FSMContext):
    await state.clear()
    await send_temp(message, "❌ Регистрация отменена.", reply_markup=main_kb())


@router.message(ClientFSM.email)
async def client_email(message: Message, state: FSMContext):
    v = message.text.strip()
    if not _email_ok(v):
        await send_temp(message, "Неверный e-mail. Пример: user@example.com", reply_markup=empty_kb())
        return
    await state.update_data(email=v)
    await _preview_form(message, state)
    await state.set_state(ClientFSM.phone)
    await ask_input(message, "📞 Телефон (например: +79991234567):")

@router.message(ClientFSM.phone)
async def client_phone(message: Message, state: FSMContext):
    v = message.text.strip()
    if not _phone_ok(v):
        await send_temp(message, "Неверный телефон. Пример: +79991234567", reply_markup=empty_kb())
        return
    await state.update_data(phone=v)
    await _preview_form(message, state)
    await state.set_state(ClientFSM.height_cm)
    await ask_input(message, "📏 Рост (см):")


@router.message(ClientFSM.height_cm)
async def client_height(message: Message, state: FSMContext):
    try:
        h = int(message.text.strip())
        if h < 50 or h > 260:
            raise ValueError()
    except Exception:
        await send_temp(message, "Введите рост в см (например: 180)", reply_markup=empty_kb())
        return
    await state.update_data(height_cm=h)
    await _preview_form(message, state)
    await state.set_state(ClientFSM.weight_kg)
    await ask_input(message, "⚖️ Вес (кг):")


@router.message(ClientFSM.weight_kg)
async def client_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", ".").strip())
        if w < 35 or w > 250:
            raise ValueError()
    except Exception:
        await send_temp(message, "Введите вес в кг (например: 82.5)", reply_markup=empty_kb())
        return
    await state.update_data(weight_kg=w)
    await _preview_form(message, state)
    await state.set_state(ClientFSM.age)
    await ask_input(message, "🎂 Возраст (полных лет):")


@router.message(ClientFSM.age)
async def client_age(message: Message, state: FSMContext):
    try:
        a = int(message.text.strip())
        if a < 10 or a > 100:
            raise ValueError()
    except Exception:
        await send_temp(message, "Введите возраст целым числом (например: 29)", reply_markup=empty_kb())
        return

    data = await state.update_data(age=a)
    await _preview_form(message, state)
    await db.user.upsert(
    where={"tg_id": message.from_user.id},
    data={
        "create": {
            "tg_id":      message.from_user.id,
            "username":   message.from_user.username,
            "first_name": data["first_name"],
            "last_name":  data["last_name"],
            "email":      data["email"],
            "phone":      data["phone"],
            "heightCm":   data.get("height_cm"),
            "weightKg":   data.get("weight_kg"),
            "age":        data.get("age"),
        },
        "update": {
            "username":   message.from_user.username,
            "first_name": data["first_name"],
            "last_name":  data["last_name"],
            "email":      data["email"],
            "phone":      data["phone"],
            "heightCm":   data.get("height_cm"),
            "weightKg":   data.get("weight_kg"),
            "age":        data.get("age"),
        },
    },
)


    await state.clear()
    await send_temp(
        message,
        "✅ Регистрация клиента завершена!",
        reply_markup=client_kb(),
    )

@router.message(F.text == "✅ Зарегистрироваться")
async def reg_start(message: Message, state: FSMContext):
    cur = await state.get_state()
    if cur and cur.startswith("ClientFSM"):
        await send_temp(message, "Продолжайте ввод данных ⬆️")
        return
    # стартуем клиентскую регистрацию (оферта)
    await client_entry(message, state)



@router.message(F.text == "❌ Отмена")
async def reg_cancel(message: Message, state: FSMContext):
    await state.clear()
    await send_temp(message, "❌ Отменено. Вы в главном меню.", reply_markup=main_kb())


@router.message(StateFilter(None), F.text.in_({"👤 Профиль", "Профиль"}))
async def profile_open(message: Message):
    u = await db.user.find_unique(where={"tg_id": message.from_user.id})
    if not u:
        await send_temp(message, "Профиль не найден. Зарегистрируйтесь", reply_markup=client_kb(False))
        return

    text = (
        "*Ваш профиль:*\n"
        f"Имя: `{u.first_name or '-'}`\n"
        f"Фамилия: `{u.last_name or '-'}`\n"
        f"E-mail: `{u.email or '-'}`\n"
        f"Телефон: `{u.phone or '-'}`\n"
        f"Рост: `{u.heightCm or '-'} см`\n"
        f"Вес: `{u.weightKg or '-'} кг`\n"
        f"Возраст: `{u.age or '-'}`\n"
        f"Текущий тариф: `{u.tariffName or 'не куплен'}`\n"
    )
    await send_temp(message, text, parse_mode="Markdown", reply_markup=CLIENT_PROFILE_KB)

@router.message(StateFilter(None), F.text == "⬅️ Назад")
async def client_back(message: Message, state: FSMContext):
    await state.clear()
    u = await db.user.find_unique(where={"tg_id": message.from_user.id})
    has_tariff = bool(u and u.tariffName)
    await send_temp(message, "🏠 Меню клиента", reply_markup=client_kb(has_tariff))

@router.message(StateFilter(EditClientFSM), F.text == "⬅️ Назад")
async def edit_client_back(message: Message, state: FSMContext):
    await state.clear()
    u = await db.user.find_unique(where={"tg_id": message.from_user.id})
    has_tariff = bool(u and u.tariffName)
    await send_temp(message, "🏠 Меню клиента", reply_markup=client_kb(has_tariff))

    

@router.message(StateFilter(None), F.text == "⬅️ На главную")
async def back_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    u = await db.user.find_unique(where={"tg_id": message.from_user.id})
    has_tariff = bool(u and u.tariffName)
    await send_temp(message, "🏠 Главное меню клиента", reply_markup=client_kb(has_tariff))



@router.message(StateFilter(None), F.text == "✏️ Изменить данные")
async def client_edit_start(message: Message, state: FSMContext):
    u = await db.user.find_unique(where={"tg_id": message.from_user.id})
    if not u:
        await send_temp(message, "Профиль не найден.")
        return

    await state.set_state(EditClientFSM.menu)
    await state.update_data(
        first_name=u.first_name or "", last_name=u.last_name or "",
        email=u.email or "", phone=u.phone or "",
        height_cm=u.heightCm or "", weight_kg=u.weightKg or "",
        age=u.age or ""
    )
    await _preview_edit_form(message, state)

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


@router.message(ClientFSM.first_name)
async def client_first(message: Message, state: FSMContext):
    v = message.text
    if not _name_ok(v):
        await send_temp(message, "Имя должно содержать только буквы, 2–30 символов.", reply_markup=empty_kb())
        return
    await state.update_data(first_name=_name_fix(v))
    await _preview_form(message, state)
    await state.set_state(ClientFSM.last_name)
    await ask_input(message, "✏️ Фамилия:")

@router.message(ClientFSM.last_name)
async def client_last(message: Message, state: FSMContext):
    v = message.text
    if not _name_ok(v):
        await send_temp(message, "Фамилия должна содержать только буквы, 2–30 символов.", reply_markup=empty_kb())
        return
    await state.update_data(last_name=_name_fix(v))
    await _preview_form(message, state)
    await state.set_state(ClientFSM.email)
    await ask_input(message, "✉️ Email:", markdown=False)


# Теперь обработчики по клику на кнопки редактирования:
def build_inline_profile_kb(data: dict) -> InlineKeyboardMarkup:
    def val(k): return data.get(k) or "-"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Имя: {val('first_name')}",    callback_data="edit_first_name"),
         InlineKeyboardButton(text=f"Фамилия: {val('last_name')}", callback_data="edit_last_name")],
        [InlineKeyboardButton(text=f"E-mail: {val('email')}",      callback_data="edit_email"),
         InlineKeyboardButton(text=f"Телефон: {val('phone')}",     callback_data="edit_phone")],
        [InlineKeyboardButton(text=f"Рост: {val('height_cm')} см", callback_data="edit_height"),
         InlineKeyboardButton(text=f"Вес: {val('weight_kg')} кг",  callback_data="edit_weight")],
        [InlineKeyboardButton(text=f"Возраст: {val('age')}",       callback_data="edit_age")],
    ])
# reg.py (рядом с build_inline_profile_kb)
def build_inline_edit_kb(data: dict) -> InlineKeyboardMarkup:
    def val(k): return data.get(k) or "-"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Имя: {val('first_name')}",    callback_data="ec_first_name"),
         InlineKeyboardButton(text=f"Фамилия: {val('last_name')}", callback_data="ec_last_name")],
        [InlineKeyboardButton(text=f"E-mail: {val('email')}",      callback_data="ec_email"),
         InlineKeyboardButton(text=f"Телефон: {val('phone')}",     callback_data="ec_phone")],
        [InlineKeyboardButton(text=f"Рост: {val('height_cm')} см", callback_data="ec_height"),
         InlineKeyboardButton(text=f"Вес: {val('weight_kg')} кг",  callback_data="ec_weight")],
        [InlineKeyboardButton(text=f"Возраст: {val('age')}",       callback_data="ec_age")],
    ])
async def _preview_edit_form(message: Message, state: FSMContext):
    data = await state.get_data()
    await send_temp(
        message,
        "✏️ *Редактирование профиля*\nВыберите, что изменить:",
        parse_mode="Markdown",
        reply_markup=build_inline_edit_kb(data)
    )


ORDER = ["first_name", "last_name", "email", "phone", "height_cm", "weight_kg", "age"]

STATE_BY_FIELD = {
    "first_name": ClientFSM.first_name,
    "last_name":  ClientFSM.last_name,
    "email":      ClientFSM.email,
    "phone":      ClientFSM.phone,
    "height_cm":  ClientFSM.height_cm,
    "weight_kg":  ClientFSM.weight_kg,
    "age":        ClientFSM.age,
}

PROMPT_BY_FIELD = {
    "first_name": "✏️ Введите ваше *имя*:",
    "last_name":  "✏️ Введите вашу *фамилию*:",
    "email":      "✉️ Введите ваш *email*:",
    "phone":      "📞 Введите ваш *телефон* (+79991234567):",
    "height_cm":  "📏 Введите ваш *рост* (см):",
    "weight_kg":  "⚖️ Введите ваш *вес* (кг):",
    "age":        "🎂 Введите ваш *возраст*:",
}

def _missing_before(target_field: str, data: dict) -> str | None:
    """Вернёт первое незаполненное поле, которое должно быть раньше target_field."""
    for f in ORDER[:ORDER.index(target_field)]:
        if not data.get(f):
            return f
    return None

@router.callback_query(F.data == "edit_first_name")
async def inline_edit_first_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClientFSM.first_name)
    await ask_input(callback.message, "✏️ Введите ваше *имя*:")
    await callback.answer()

@router.callback_query(F.data == "edit_last_name")
async def inline_edit_last_name(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("last_name", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.last_name)
    await callback.message.answer(PROMPT_BY_FIELD["last_name"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()

@router.callback_query(F.data == "edit_email")
async def inline_edit_email(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("email", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.email)
    await callback.message.answer(PROMPT_BY_FIELD["email"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()

@router.callback_query(F.data == "edit_phone")
async def inline_edit_phone(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("phone", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.phone)
    await callback.message.answer(PROMPT_BY_FIELD["phone"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()


from aiogram.types import CallbackQuery

@router.callback_query(F.data == "edit_height")
async def inline_edit_height(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("height_cm", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.height_cm)
    await callback.message.answer(PROMPT_BY_FIELD["height_cm"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()

@router.callback_query(F.data == "edit_weight")
async def inline_edit_weight(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("weight_kg", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.weight_kg)
    await callback.message.answer(PROMPT_BY_FIELD["weight_kg"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()

@router.callback_query(F.data == "edit_age")
async def inline_edit_age(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    miss = _missing_before("age", data)
    if miss:
        await callback.answer("Сначала заполните предыдущее поле.", show_alert=True)
        await state.set_state(STATE_BY_FIELD[miss])
        await ask_input(callback.message, PROMPT_BY_FIELD[miss])
        return
    await state.set_state(ClientFSM.age)
    await callback.message.answer(PROMPT_BY_FIELD["age"], parse_mode="Markdown", reply_markup=empty_kb())
    await callback.answer()


@router.callback_query(F.data == "submit_register")
async def inline_submit_register(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    for field in ORDER:
        if not data.get(field):
            await callback.answer("Сначала заполните все поля.", show_alert=True)
            await state.set_state(STATE_BY_FIELD[field])
            await ask_input(callback.message, PROMPT_BY_FIELD[field])
            return
    await callback.answer("Готово! Жмите кнопку «✅ Зарегистрироваться».", show_alert=True)

from aiogram.types import CallbackQuery

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_first_name")
async def ec_first_name(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.first_name)
    await cb.message.answer("✏️ Введите новое *имя*:", parse_mode="Markdown", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_last_name")
async def ec_last_name(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.last_name)
    await cb.message.answer("✏️ Введите новую *фамилию*:", parse_mode="Markdown", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_email")
async def ec_email(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.email)
    await cb.message.answer("✉️ Введите новый *email*:", parse_mode="Markdown", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_phone")
async def ec_phone(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.phone)
    await cb.message.answer("📞 Введите новый *телефон* (+79991234567):", parse_mode="Markdown", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_height")
async def ec_height(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.height_cm)
    await cb.message.answer("📏 Рост (см):", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_weight")
async def ec_weight(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.weight_kg)
    await cb.message.answer("⚖️ Вес (кг):", reply_markup=cancel_kb())
    await cb.answer()

@router.callback_query(StateFilter(EditClientFSM.menu), F.data == "ec_age")
async def ec_age(cb: CallbackQuery, state: FSMContext):
    await state.set_state(EditClientFSM.age)
    await cb.message.answer("🎂 Возраст (лет):", reply_markup=cancel_kb())
    await cb.answer()
@router.message(EditClientFSM.first_name)
async def edit_first_name_set(message: Message, state: FSMContext):
    v = message.text
    if not _name_ok(v):
        await send_temp(message, "Имя должно содержать только буквы, 2–30 символов.", reply_markup=cancel_kb())
        return
    v = _name_fix(v)
    await db.user.update(where={"tg_id": message.from_user.id}, data={"first_name": v})
    await state.update_data(first_name=v)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.last_name)
async def edit_last_name_set(message: Message, state: FSMContext):
    v = message.text
    if not _name_ok(v):
        await send_temp(message, "Фамилия должна содержать только буквы, 2–30 символов.", reply_markup=cancel_kb())
        return
    v = _name_fix(v)
    await db.user.update(where={"tg_id": message.from_user.id}, data={"last_name": v})
    await state.update_data(last_name=v)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.email)
async def edit_email_set(message: Message, state: FSMContext):
    v = message.text.strip()
    if not _email_ok(v):
        await send_temp(message, "Неверный e-mail. Пример: user@example.com", reply_markup=cancel_kb())
        return
    await db.user.update(where={"tg_id": message.from_user.id}, data={"email": v})
    await state.update_data(email=v)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.phone)
async def edit_phone_set(message: Message, state: FSMContext):
    v = message.text.strip()
    if not _phone_ok(v):
        await send_temp(message, "Неверный телефон. Пример: +79991234567", reply_markup=cancel_kb())
        return
    await db.user.update(where={"tg_id": message.from_user.id}, data={"phone": v})
    await state.update_data(phone=v)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.height_cm)
async def edit_height_set(message: Message, state: FSMContext):
    try:
        h = int(message.text.strip())
        if h < 120 or h > 230: raise ValueError()
    except Exception:
        await send_temp(message, "Введите рост в см (например: 180)", reply_markup=cancel_kb())
        return
    await db.user.update(where={"tg_id": message.from_user.id}, data={"heightCm": h})
    await state.update_data(height_cm=h)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.weight_kg)
async def edit_weight_set(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(",", ".").strip())
        if w < 35 or w > 250: raise ValueError()
    except Exception:
        await send_temp(message, "Введите вес в кг (например: 82.5)", reply_markup=cancel_kb())
        return
    await db.user.update(where={"tg_id": message.from_user.id}, data={"weightKg": w})
    await state.update_data(weight_kg=w)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)

@router.message(EditClientFSM.age)
async def edit_age_set(message: Message, state: FSMContext):
    try:
        a = int(message.text.strip())
        if a < 10 or a > 80: raise ValueError()
    except Exception:
        await send_temp(message, "Введите возраст целым числом (например: 29)", reply_markup=cancel_kb())
        return
    await db.user.update(where={"tg_id": message.from_user.id}, data={"age": a})
    await state.update_data(age=a)
    await state.set_state(EditClientFSM.menu)
    await _preview_edit_form(message, state)
