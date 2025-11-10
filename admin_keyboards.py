from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


def get_admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Изменить сообщения", callback_data="admin_messages"))
    builder.row(InlineKeyboardButton(text="🤸 Управление позами", callback_data="admin_poses"))
    builder.row(InlineKeyboardButton(text="🌆 Управление сценами", callback_data="admin_scenes"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))  
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
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

def get_pose_elements_keyboard(pose_id: str, elements: List) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if elem else '⬜'} {elem.name}",
            callback_data=f"pose_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="pose_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_pose"))
    return builder.as_markup()


def get_scene_elements_keyboard(scene_id: str, elements: List) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if elem else '⬜'} {elem.name}",
            callback_data=f"scene_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="scene_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_scene"))
    return builder.as_markup()