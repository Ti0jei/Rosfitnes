# helpers.py
import asyncio
from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardMarkup

# Временное хранилище ID сообщений на пользователя (если понадобится)
_temp_message_ids = {}  # user_id → message_id


async def send_temp(message: Message, text: str, *, reply_markup=None, parse_mode=None, delay: int = 30):
    """
    По умолчанию показываем ПУСТУЮ reply-клавиатуру, чтобы НЕ всплывала системная.
    """
    if reply_markup is None:
        reply_markup = ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True, is_persistent=False)
    return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def _expire_message(bot: Bot, chat_id: int, message_id: int, delay: int = 30):
    """Удаляет сообщение через delay секунд (если не удалено раньше)."""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def send_keep(message: Message, text: str, *, reply_markup=None, parse_mode=None):
    """
    Сообщение без удаления. Используй для экранов меню и навигации.
    (reply_markup передаём вручную — тут по умолчанию ничего не подставляем)
    """
    return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def send_ephemeral(message: Message, text: str, *, reply_markup=None, parse_mode=None):
    """
    Одноразовое сообщение без хранения ID — не очищает другие.
    (reply_markup передаём вручную — тут по умолчанию ничего не подставляем)
    """
    return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
