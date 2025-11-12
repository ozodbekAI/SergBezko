from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from database import async_session_maker
from database.repositories import (UserRepository, TaskRepository, PaymentRepository, 
                                   BotMessageRepository, AdminLogRepository)
from states import AdminMessageStates, AdminUserStates
from admin_keyboards import (get_admin_main_menu, get_message_selection_keyboard,
                             get_media_type_keyboard, get_admin_back_keyboard,
                             get_user_management_menu, get_user_detail_keyboard,
                             get_balance_action_keyboard, get_cancel_keyboard, 
                             get_user_list_keyboard)
from keyboards import get_main_menu
import logging

logger = logging.getLogger(__name__)
router = Router(name="admin")


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    if callback.message.text is None:
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Delete failed: {e}")
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Edit failed: {e}")
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def check_admin(callback: CallbackQuery) -> bool:
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        is_admin = await user_repo.is_admin(callback.from_user.id)
    return is_admin


async def check_admin_message(message: Message) -> bool:
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        is_admin = await user_repo.is_admin(message.from_user.id)
    return is_admin



@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not await check_admin_message(message):
        await message.answer("❌ У вас нет доступа к админ панели.")
        return
    
    await state.clear()
    await message.answer(
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    await safe_edit_text(
        callback,
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_menu()
    )



@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        payment_repo = PaymentRepository(session)
        
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        total_tasks = await task_repo.get_total_tasks()
        completed_tasks = await task_repo.get_completed_tasks()
        total_payments = await payment_repo.get_total_payments()
        total_credits = await payment_repo.get_total_credits_sold()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных (30 дней): <b>{active_users}</b>\n\n"
        f"📋 Всего задач: <b>{total_tasks}</b>\n"
        f"✅ Завершенных: <b>{completed_tasks}</b>\n\n"
        f"💳 Успешных платежей: <b>{total_payments}</b>\n"
        f"🎁 Продано кредитов: <b>{total_credits}</b>"
    )
    
    await safe_edit_text(callback, stats_text, reply_markup=get_admin_back_keyboard())



@router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        banned_count = await user_repo.get_banned_count()
    
    await safe_edit_text(
        callback,
        f"👥 <b>Управление пользователями</b>\n\n"
        f"📊 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных (30 дней): <b>{active_users}</b>\n"
        f"🚫 Заблокированных: <b>{banned_count}</b>\n\n"
        f"Выберите действие:",
        reply_markup=get_user_management_menu()
    )



@router.callback_query(F.data == "user_search")
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.set_state(AdminUserStates.searching_user)
    
    await safe_edit_text(
        callback,
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите для поиска:\n"
        "• Username (без @)\n"
        "• Telegram ID\n"
        "• Имя пользователя\n\n"
        "<i>Например: john_doe или 123456789 или Иван</i>",
        reply_markup=get_cancel_keyboard("admin_users")
    )


@router.message(AdminUserStates.searching_user, F.text)
async def user_search_process(message: Message, state: FSMContext):
    search_query = message.text.strip()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        users = await user_repo.search_users(search_query)
    
    if not users:
        await message.answer(
            f"❌ Пользователи не найдены по запросу: <code>{search_query}</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard("admin_users")
        )
        return
    
    if len(users) == 1:
        user = users[0]
        await state.clear()
        await show_user_detail(message, user)
    else:
        await state.clear()
        await message.answer(
            f"🔍 Найдено пользователей: <b>{len(users)}</b>\n\n"
            f"Выберите пользователя:",
            parse_mode="HTML",
            reply_markup=get_user_list_keyboard(users)
        )


async def show_user_detail(message_or_callback, user):
    status = "🚫 Заблокирован" if user.is_banned else "✅ Активен"
    admin_status = "👑 Администратор" if user.is_admin else "👤 Пользователь"
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Username:</b> {'@' + user.username if user.username else 'Не указан'}\n"
        f"<b>Имя:</b> {user.first_name or 'Не указано'}\n"
        f"<b>Фамилия:</b> {user.last_name or 'Не указана'}\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Роль:</b> {admin_status}\n"
        f"<b>Баланс:</b> 💰 <b>{user.balance}</b> кредитов\n\n"
        f"<b>Зарегистрирован:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>Последняя активность:</b> {user.last_activity.strftime('%d.%m.%Y %H:%M')}"
    )
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(
            text,
            reply_markup=get_user_detail_keyboard(user.telegram_id, user.is_banned)
        )
    else:
        await safe_edit_text(
            message_or_callback,
            text,
            reply_markup=get_user_detail_keyboard(user.telegram_id, user.is_banned)
        )


@router.callback_query(F.data.startswith("user_view_"))
async def user_view_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    user_id = int(callback.data.replace("user_view_", ""))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_telegram_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await show_user_detail(callback, user)


@router.callback_query(F.data.startswith("user_ban_"))
async def user_ban_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    user_id = int(callback.data.replace("user_ban_", ""))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.ban_user(user_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "ban_user",
            f"Banned user {user_id}"
        )
    
    await callback.answer("✅ Пользователь заблокирован")
    await show_user_detail(callback, user)


@router.callback_query(F.data.startswith("user_unban_"))
async def user_unban_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    user_id = int(callback.data.replace("user_unban_", ""))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.unban_user(user_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "unban_user",
            f"Unbanned user {user_id}"
        )
    
    await callback.answer("✅ Пользователь разблокирован")
    await show_user_detail(callback, user)


@router.callback_query(F.data.startswith("user_balance_"))
async def user_balance_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    user_id = int(callback.data.replace("user_balance_", ""))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_telegram_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await safe_edit_text(
        callback,
        f"💰 <b>Изменение баланса</b>\n\n"
        f"Пользователь: {'@' + user.username if user.username else f'ID: {user.telegram_id}'}\n"
        f"Текущий баланс: <b>{user.balance}</b> кредитов\n\n"
        f"Выберите действие:",
        reply_markup=get_balance_action_keyboard(user_id)
    )


@router.callback_query((F.data.startswith("balance_add_")) | (F.data.startswith("balance_subtract_")))
async def balance_action_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    action = "add" if callback.data.startswith("balance_add_") else "subtract"
    user_id = int(callback.data.split("_")[-1])
    
    await state.set_state(AdminUserStates.adding_credits)
    await state.update_data(user_id=user_id, action=action)
    
    action_text = "добавить" if action == "add" else "убавить"
    
    await safe_edit_text(
        callback,
        f"💰 <b>Изменение баланса</b>\n\n"
        f"Введите количество кредитов для операции <b>{action_text}</b>:\n\n"
        f"<i>Например: 100</i>",
        reply_markup=get_cancel_keyboard(f"user_balance_{user_id}")
    )


@router.message(AdminUserStates.adding_credits, F.text)
async def balance_action_process(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Количество должно быть положительным числом")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return
    
    data = await state.get_data()
    user_id = data["user_id"]
    action = data["action"]
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        
        if action == "subtract":
            amount = -amount
        
        user = await user_repo.update_balance(user_id, amount)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "update_balance",
            f"{'Added' if amount > 0 else 'Subtracted'} {abs(amount)} credits to user {user_id}"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Баланс успешно изменен!\n\n"
        f"Новый баланс: <b>{user.balance}</b> кредитов",
        parse_mode="HTML",
        reply_markup=get_user_detail_keyboard(user_id, user.is_banned)
    )


@router.callback_query(F.data.startswith("user_tasks_"))
async def user_tasks_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    user_id = int(callback.data.replace("user_tasks_", ""))
    
    async with async_session_maker() as session:
        task_repo = TaskRepository(session)
        tasks = await task_repo.get_user_tasks(user_id, limit=20)
        
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_telegram_id(user_id)
    
    if not tasks:
        await safe_edit_text(
            callback,
            f"📊 <b>Статистика задач</b>\n\n"
            f"У пользователя {'@' + user.username if user.username else f'ID: {user_id}'} нет задач.",
            reply_markup=get_user_detail_keyboard(user_id, user.is_banned)
        )
        return
    
    completed = sum(1 for t in tasks if t.status.value == "completed")
    failed = sum(1 for t in tasks if t.status.value == "failed")
    pending = sum(1 for t in tasks if t.status.value == "pending")
    
    text = (
        f"📊 <b>Статистика задач</b>\n\n"
        f"Пользователь: {'@' + user.username if user.username else f'ID: {user_id}'}\n\n"
        f"✅ Завершено: <b>{completed}</b>\n"
        f"❌ Ошибки: <b>{failed}</b>\n"
        f"⏳ В обработке: <b>{pending}</b>\n"
        f"📋 Всего: <b>{len(tasks)}</b>\n\n"
        f"<b>Последние задачи:</b>\n"
    )
    
    for task in tasks[:10]:
        status_emoji = {"completed": "✅", "failed": "❌", "pending": "⏳", "processing": "🔄"}
        emoji = status_emoji.get(task.status.value, "❓")
        text += f"{emoji} {task.task_type.value} - {task.created_at.strftime('%d.%m %H:%M')}\n"
    
    await safe_edit_text(
        callback,
        text,
        reply_markup=get_user_detail_keyboard(user_id, user.is_banned)
    )


@router.callback_query(F.data == "user_banned_list")
async def user_banned_list_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        banned_users = await user_repo.get_banned_users(limit=20)
    
    if not banned_users:
        await safe_edit_text(
            callback,
            "🚫 <b>Заблокированные пользователи</b>\n\n"
            "Заблокированных пользователей нет.",
            reply_markup=get_cancel_keyboard("admin_users")
        )
        return
    
    await safe_edit_text(
        callback,
        f"🚫 <b>Заблокированные пользователи</b>\n\n"
        f"Всего: <b>{len(banned_users)}</b>\n\n"
        f"Выберите пользователя:",
        reply_markup=get_user_list_keyboard(banned_users)
    )


@router.callback_query((F.data == "user_all_list") | (F.data.startswith("user_list_")))
async def user_all_list_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    offset = 0
    if callback.data.startswith("user_list_"):
        offset = int(callback.data.replace("user_list_", ""))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_all_users(limit=20, offset=offset)
    
    if not users:
        await safe_edit_text(
            callback,
            "👥 <b>Все пользователи</b>\n\n"
            "Пользователи не найдены.",
            reply_markup=get_cancel_keyboard("admin_users")
        )
        return
    
    await safe_edit_text(
        callback,
        f"👥 <b>Все пользователи</b>\n\n"
        f"Показано с {offset + 1} по {offset + len(users)}\n\n"
        f"Выберите пользователя:",
        reply_markup=get_user_list_keyboard(users, offset)
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin stats callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        payment_repo = PaymentRepository(session)
        
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        total_balance = await user_repo.get_total_balance()
        total_tasks = await task_repo.get_total_tasks()
        completed_tasks = await task_repo.get_completed_tasks()
        total_payments = await payment_repo.get_total_payments()
        total_credits = await payment_repo.get_total_credits_sold()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных (30 дней): <b>{active_users}</b>\n"
        f"💰 Общий баланс: <b>{total_balance}</b> кредитов\n\n"
        f"📋 Всего задач: <b>{total_tasks}</b>\n"
        f"✅ Завершенных: <b>{completed_tasks}</b>\n\n"
        f"💳 Успешных платежей: <b>{total_payments}</b>\n"
        f"🎁 Продано кредитов: <b>{total_credits}</b>"
    )
    
    await safe_edit_text(
        callback,
        stats_text,
        reply_markup=get_admin_back_keyboard()
    )



@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin stats callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        payment_repo = PaymentRepository(session)
        
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        total_balance = await user_repo.get_total_balance()
        total_tasks = await task_repo.get_total_tasks()
        completed_tasks = await task_repo.get_completed_tasks()
        total_payments = await payment_repo.get_total_payments()
        total_credits = await payment_repo.get_total_credits_sold()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных (30 дней): <b>{active_users}</b>\n"
        f"💰 Общий баланс: <b>{total_balance}</b> кредитов\n\n"
        f"📋 Всего задач: <b>{total_tasks}</b>\n"
        f"✅ Завершенных: <b>{completed_tasks}</b>\n\n"
        f"💳 Успешных платежей: <b>{total_payments}</b>\n"
        f"🎁 Продано кредитов: <b>{total_credits}</b>"
    )
    
    await safe_edit_text(
        callback,
        stats_text,
        reply_markup=get_admin_back_keyboard()
    )


@router.callback_query(F.data == "admin_messages")
async def admin_messages_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    await safe_edit_text(
        callback,
        "📝 <b>Управление сообщениями бота</b>\n\n"
        "Выберите сообщение для редактирования:",
        reply_markup=get_message_selection_keyboard()
    )


@router.callback_query(F.data.startswith("edit_msg_"))
async def select_message_to_edit(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    message_key = callback.data.replace("edit_msg_", "")

    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        bot_msg = await msg_repo.get_message(message_key)
    
    current_text = bot_msg.text if bot_msg else "Не установлено"
    media_info = ""
    if bot_msg and bot_msg.media_type:
        media_info = f"\n🔎 Медиа: {bot_msg.media_type}"
    
    await state.set_state(AdminMessageStates.entering_text)
    await state.update_data(message_key=message_key)
    
    await safe_edit_text(
        callback,
        f"✏️ <b>Редактирование сообщения</b>\n\n"
        f"Текущий текст:\n{current_text}{media_info}\n\n"
        f"Введите новый текст сообщения:",
        reply_markup=get_admin_back_keyboard()
    )


@router.message(AdminMessageStates.entering_text, F.text)
async def message_text_received(message: Message, state: FSMContext):
    data = await state.get_data()
    
    await state.update_data(new_text=message.text)
    await state.set_state(AdminMessageStates.uploading_media)
    
    await message.answer(
        "✅ Текст получен!\n\n"
        "Теперь выберите тип медиа (или пропустите):",
        reply_markup=get_media_type_keyboard()
    )


@router.callback_query(AdminMessageStates.uploading_media, F.data.startswith("media_"))
async def media_type_selected(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    media_type = callback.data.replace("media_", "")
    
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data["new_text"]
    
    if media_type == "none":
        async with async_session_maker() as session:
            msg_repo = BotMessageRepository(session)
            await msg_repo.set_message(message_key, new_text, None, None)
            
            log_repo = AdminLogRepository(session)
            await log_repo.log_action(
                callback.from_user.id,
                "update_message",
                f"Updated message: {message_key}"
            )
        
        await safe_edit_text(
            callback,
            "✅ Сообщение успешно обновлено!",
            reply_markup=get_admin_main_menu()
        )
        await state.clear()
    else:
        await state.update_data(media_type=media_type)
        await safe_edit_text(
            callback,
            f"📤 Теперь отправьте {media_type} (фото или видео):",
            reply_markup=get_admin_back_keyboard()
        )


@router.message(AdminMessageStates.uploading_media, F.photo | F.video)
async def media_received(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data["new_text"]

    if message.photo:
        file_id = message.photo[-1].file_id
        actual_media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        actual_media_type = "video"
    else:
        await message.answer("❌ Неверный формат. Отправьте фото или видео.")
        return
    
    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        await msg_repo.set_message(message_key, new_text, actual_media_type, file_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "update_message_with_media",
            f"Updated message: {message_key} with {actual_media_type}"
        )
    
    await message.answer(
        "✅ Сообщение с медиа успешно обновлено!",
        reply_markup=get_admin_main_menu()
    )
    await state.clear()