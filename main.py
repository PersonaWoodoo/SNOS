import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db import (
    init_db, remember_user, add_admin, remove_admin, get_admin,
    list_admins, stats, log_action
)
from bot.keyboards import main_menu, admin_menu, back_menu
from bot.states import AdminFlow

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "9117753958:AAGKOWe_ZaL6RsfdxtymoUlXgAOqH_xzm38").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8959461245"))
DB_PATH = os.getenv("DB_PATH", "bot.sqlite3")

PERMISSIONS = {
    "stats": "Статистика",
    "manage_admins": "Управление администраторами",
    "logs": "Просмотр журнала",
    "moderation": "Модерация обращений",
}

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def has_permission(user_id: int, permission: str) -> bool:
    if is_owner(user_id):
        return True
    return permission in await get_admin(DB_PATH, user_id)

async def admin_keyboard():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить администратора", callback_data="admin_add")
    b.button(text="➖ Удалить администратора", callback_data="admin_remove")
    b.button(text="📃 Список администраторов", callback_data="admin_list")
    b.button(text="⬅️ Назад", callback_data="home")
    b.adjust(1)
    return b.as_markup()

async def main():
    if not TOKEN or TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise RuntimeError("Укажи BOT_TOKEN в .env. Не отправляй токен в чат.")
    await init_db(DB_PATH, OWNER_ID)
    bot = Bot(TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(CommandStart())
    async def start(message: Message):
        u = message.from_user
        await remember_user(DB_PATH, u.id, u.username, u.first_name)
        await message.answer(
            "🤖 <b>Главное меню</b>\n\nВыбери нужный раздел:",
            reply_markup=main_menu(),
            parse_mode="HTML",
        )

    @dp.message(Command("id"))
    async def show_id(message: Message):
        await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

    @dp.callback_query(F.data == "home")
    async def home(call: CallbackQuery):
        await call.message.edit_text("🤖 <b>Главное меню</b>\n\nВыбери раздел:", reply_markup=main_menu(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "admin")
    async def admin_panel(call: CallbackQuery):
        uid = call.from_user.id
        if not (is_owner(uid) or await has_permission(uid, "stats") or await has_permission(uid, "manage_admins")):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await call.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_menu(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "admins")
    async def admins_panel(call: CallbackQuery):
        if not await has_permission(call.from_user.id, "manage_admins"):
            await call.answer("Управлять администраторами может только владелец.", show_alert=True)
            return
        await call.message.edit_text("👥 <b>Управление администраторами</b>", reply_markup=await admin_keyboard(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "admin_add")
    async def admin_add_start(call: CallbackQuery, state: FSMContext):
        if not is_owner(call.from_user.id):
            await call.answer("Добавлять администраторов может только главный администратор.", show_alert=True)
            return
        await state.set_state(AdminFlow.waiting_for_user_id)
        await call.message.answer("Отправь Telegram ID нового администратора числом.")
        await call.answer()

    @dp.message(AdminFlow.waiting_for_user_id)
    async def admin_add_id(message: Message, state: FSMContext):
        if not is_owner(message.from_user.id):
            await state.clear()
            return
        try:
            target_id = int(message.text.strip())
            if target_id <= 0 or target_id == OWNER_ID:
                raise ValueError
        except (ValueError, AttributeError):
            await message.answer("Нужен корректный числовой Telegram ID. Попробуй ещё раз.")
            return
        await state.update_data(target_id=target_id)
        b = InlineKeyboardBuilder()
        for key, label in PERMISSIONS.items():
            b.button(text=f"☑️ {label}", callback_data=f"perm:{key}")
        b.button(text="✅ Сохранить администратора", callback_data="admin_save")
        b.button(text="❌ Отмена", callback_data="admin_cancel")
        b.adjust(1)
        await state.update_data(selected_permissions=[])
        await state.set_state(AdminFlow.waiting_for_permissions)
        await message.answer("Выбери разрешения. Нажатие переключает право:", reply_markup=b.as_markup())

    @dp.callback_query(AdminFlow.waiting_for_permissions, F.data.startswith("perm:"))
    async def toggle_permission(call: CallbackQuery, state: FSMContext):
        if not is_owner(call.from_user.id):
            await call.answer("Нет доступа.", show_alert=True)
            return
        key = call.data.split(":", 1)[1]
        if key not in PERMISSIONS:
            await call.answer()
            return
        data = await state.get_data()
        selected = set(data.get("selected_permissions", []))
        selected.symmetric_difference_update({key})
        await state.update_data(selected_permissions=list(selected))
        b = InlineKeyboardBuilder()
        for k, label in PERMISSIONS.items():
            prefix = "✅" if k in selected else "▫️"
            b.button(text=f"{prefix} {label}", callback_data=f"perm:{k}")
        b.button(text="💾 Сохранить", callback_data="admin_save")
        b.button(text="❌ Отмена", callback_data="admin_cancel")
        b.adjust(1)
        await call.message.edit_reply_markup(reply_markup=b.as_markup())
        await call.answer("Право обновлено")

    @dp.callback_query(AdminFlow.waiting_for_permissions, F.data == "admin_save")
    async def admin_save(call: CallbackQuery, state: FSMContext):
        if not is_owner(call.from_user.id):
            await call.answer("Нет доступа.", show_alert=True)
            return
        data = await state.get_data()
        target_id = data["target_id"]
        permissions = data.get("selected_permissions", [])
        await add_admin(DB_PATH, target_id, permissions, call.from_user.id)
        await state.clear()
        await call.message.edit_text(f"✅ Администратор <code>{target_id}</code> сохранён.\nПрава: {', '.join(PERMISSIONS[p] for p in permissions) or 'нет'}", reply_markup=back_menu(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "admin_cancel")
    async def admin_cancel(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.edit_text("❌ Действие отменено.", reply_markup=back_menu())
        await call.answer()

    @dp.callback_query(F.data == "admin_remove")
    async def admin_remove_start(call: CallbackQuery, state: FSMContext):
        if not is_owner(call.from_user.id):
            await call.answer("Удалять администраторов может только главный администратор.", show_alert=True)
            return
        await state.set_state(AdminFlow.waiting_for_remove_id)
        await call.message.answer("Отправь Telegram ID администратора, которого нужно удалить.")
        await call.answer()

    @dp.message(AdminFlow.waiting_for_remove_id)
    async def admin_remove_id(message: Message, state: FSMContext):
        if not is_owner(message.from_user.id):
            await state.clear()
            return
        try:
            target_id = int(message.text.strip())
            if target_id == OWNER_ID or target_id <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            await message.answer("Некорректный ID. Главного администратора удалить нельзя.")
            return
        await remove_admin(DB_PATH, target_id, message.from_user.id)
        await state.clear()
        await message.answer(f"Администратор {target_id} удалён.")

    @dp.callback_query(F.data == "admin_list")
    async def admin_list(call: CallbackQuery):
        if not is_owner(call.from_user.id):
            await call.answer("Список администраторов доступен только главному администратору.", show_alert=True)
            return
        rows = await list_admins(DB_PATH)
        if not rows:
            text = "Список дополнительных администраторов пуст."
        else:
            text = "👥 <b>Администраторы</b>\n" + "\n".join(
                f"• <code>{r[0]}</code> — {', '.join(PERMISSIONS.get(p, p) for p in r[1].split(',') if p) or 'без прав'}"
                for r in rows
            )
        await call.message.edit_text(text, reply_markup=back_menu(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "stats")
    async def show_stats(call: CallbackQuery):
        if not await has_permission(call.from_user.id, "stats"):
            await call.answer("Нет доступа.", show_alert=True)
            return
        users, admins = await stats(DB_PATH)
        await call.message.edit_text(f"📊 <b>Статистика</b>\nПользователей: {users}\nАдминистраторов: {admins}", reply_markup=back_menu(), parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data == "logs_info")
    async def logs_info(call: CallbackQuery):
        if not await has_permission(call.from_user.id, "logs"):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await call.message.edit_text("📋 Журнал действий будет подключён следующим этапом.", reply_markup=back_menu())
        await call.answer()

    @dp.callback_query(F.data == "search_info")
    async def search_info(call: CallbackQuery):
        await call.message.edit_text(
            "🔎 <b>Поиск</b>\n\nНа следующем этапе добавим поиск по публичным профилям и открытым данным. "
            "Поиск частных адресов, закрытых данных или сбор досье на людей не поддерживается.",
            reply_markup=back_menu(), parse_mode="HTML"
        )
        await call.answer()

    @dp.callback_query(F.data == "my_resources")
    async def resources_info(call: CallbackQuery):
        await call.message.edit_text(
            "📢 Здесь будут инструменты управления собственными каналами и чатами: "
            "настройки, проверка прав бота и модерация.",
            reply_markup=back_menu()
        )
        await call.answer()

    @dp.callback_query(F.data == "report_info")
    async def report_info(call: CallbackQuery):
        await call.message.edit_text(
            "🛡️ Для жалоб на нарушения используем официальные инструменты Telegram. "
            "Бот не будет запускать массовые или ложные жалобы и не будет атаковать чужие аккаунты, каналы или чаты.",
            reply_markup=back_menu()
        )
        await call.answer()

    @dp.message()
    async def fallback(message: Message):
        await message.answer("Используй /start, чтобы открыть меню.", reply_markup=main_menu())

    print(f"Bot started. Owner ID: {OWNER_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
