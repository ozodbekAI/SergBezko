from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.row(InlineKeyboardButton(text="📝 Изменить сообщения", callback_data="admin_messages"))
    builder.row(InlineKeyboardButton(text="🤸 Управление позами", callback_data="admin_poses"))
    builder.row(InlineKeyboardButton(text="🌆 Управление сценами", callback_data="admin_scenes"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))  
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    return builder.as_markup()


def get_user_management_menu() -> InlineKeyboardMarkup:
    """User boshqaruv asosiy menyusi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="user_search"))
    builder.row(InlineKeyboardButton(text="🚫 Заблокированные пользователи", callback_data="user_banned_list"))
    builder.row(InlineKeyboardButton(text="👥 Все пользователи (последние 20)", callback_data="user_all_list"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_user_detail_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Bitta user uchun batafsil klaviatura"""
    builder = InlineKeyboardBuilder()
    
    if is_banned:
        builder.row(InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"user_unban_{user_id}"))
    else:
        builder.row(InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"user_ban_{user_id}"))
    
    builder.row(InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"user_balance_{user_id}"))
    builder.row(InlineKeyboardButton(text="📊 Статистика задач", callback_data=f"user_tasks_{user_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin_users"))
    return builder.as_markup()


def get_balance_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Balans o'zgartirish klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data=f"balance_add_{user_id}"),
        InlineKeyboardButton(text="➖ Убавить", callback_data=f"balance_subtract_{user_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"user_view_{user_id}"))
    return builder.as_markup()


def get_cancel_keyboard(back_to: str = "admin_users") -> InlineKeyboardMarkup:
    """Bekor qilish klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=back_to))
    return builder.as_markup()


def get_user_list_keyboard(users: List, offset: int = 0) -> InlineKeyboardMarkup:
    """Userlar ro'yxati klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    for user in users:
        status = "🚫" if user.is_banned else "✅"
        username = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        builder.row(InlineKeyboardButton(
            text=f"{status} {username} ({user.balance} кр.)",
            callback_data=f"user_view_{user.telegram_id}"
        ))
    
    # Pagination (agar kerak bo'lsa)
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"user_list_{offset-20}"))
    if len(users) == 20:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"user_list_{offset+20}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users"))
    return builder.as_markup()


def get_message_selection_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Стартовое сообщение", callback_data="edit_msg_start"))
    builder.row(InlineKeyboardButton(text="📦 Карточка товара", callback_data="edit_msg_product_card"))
    builder.row(InlineKeyboardButton(text="👗 Нормализация", callback_data="edit_msg_normalize"))
    builder.row(InlineKeyboardButton(text="🎬 Видео", callback_data="edit_msg_video"))
    builder.row(InlineKeyboardButton(text="📸 Фото", callback_data="edit_msg_photo"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_media_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🖼 Фото", callback_data="media_photo"))
    builder.row(InlineKeyboardButton(text="🎥 Видео", callback_data="media_video"))
    builder.row(InlineKeyboardButton(text="❌ Без медиа", callback_data="media_none"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_messages"))
    return builder.as_markup()


def get_pose_management_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить элемент", callback_data="pose_add"))
    builder.row(InlineKeyboardButton(text="📋 Список элементов", callback_data="pose_list"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить элемент", callback_data="pose_delete"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_scene_management_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить элемент", callback_data="scene_add"))
    builder.row(InlineKeyboardButton(text="📋 Список элементов", callback_data="scene_list"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить элемент", callback_data="scene_delete"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_pose_groups_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🧍 Стоячие", callback_data="pose_group_standing"))
    builder.row(InlineKeyboardButton(text="🪑 Сидячие", callback_data="pose_group_sitting"))
    builder.row(InlineKeyboardButton(text="⚡ Динамические", callback_data="pose_group_dynamic"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_poses"))
    return builder.as_markup()


def get_scene_groups_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Внутренние", callback_data="scene_group_indoor"))
    builder.row(InlineKeyboardButton(text="🌳 Наружные", callback_data="scene_group_outdoor"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_scenes"))
    return builder.as_markup()


def get_element_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎬 Действие", callback_data="elem_type_action"))
    builder.row(InlineKeyboardButton(text="😊 Настроение", callback_data="elem_type_mood"))
    builder.row(InlineKeyboardButton(text="🎨 Стиль", callback_data="elem_type_style"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_poses"))
    return builder.as_markup()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
    )
    return builder.as_markup()


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return builder.as_markup()