from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🔎 Поиск по открытым данным", callback_data="search_info")
    b.button(text="📢 Мои каналы и чаты", callback_data="my_resources")
    b.button(text="🛡️ Подать жалобу в Telegram", callback_data="report_info")
    b.button(text="⚙️ Админ-панель", callback_data="admin")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

def admin_menu():
    b = InlineKeyboardBuilder()
    b.button(text="👥 Администраторы", callback_data="admins")
    b.button(text="📊 Статистика", callback_data="stats")
    b.button(text="📋 Журнал действий", callback_data="logs_info")
    b.button(text="⬅️ Назад", callback_data="home")
    b.adjust(2, 1, 1)
    return b.as_markup()

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")]
    ])
