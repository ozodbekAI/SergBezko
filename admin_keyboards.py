from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.row(InlineKeyboardButton(text="📝 Изменить сообщения", callback_data="admin_messages"))
    builder.row(InlineKeyboardButton(text="🎬 Сценарии видео", callback_data="admin_video_scenarios"))
    builder.row(InlineKeyboardButton(text="👤 Типы моделей", callback_data="admin_model_types"))
    builder.row(InlineKeyboardButton(text="🤸 Управление позами", callback_data="admin_poses"))
    builder.row(InlineKeyboardButton(text="🌆 Управление сценами", callback_data="admin_scenes"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    return builder.as_markup()


def get_scene_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить локацию", callback_data="scene_add_location"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать промпт", callback_data="scene_edit_prompt_menu"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить промпт", callback_data="scene_delete_prompt_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_scene_groups_admin_list(groups: List, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for group in groups:
        if action == "edit":
            callback = f"scene_admin_edit_group_{group.id}"
        elif action == "delete":
            callback = f"scene_admin_delete_group_{group.id}"
        else:
            callback = f"scene_admin_view_group_{group.id}"
        
        builder.row(InlineKeyboardButton(text=group.name, callback_data=callback))
    
    if action == "edit":
        back_callback = "scene_edit_prompt_menu"
    elif action == "delete":
        back_callback = "scene_delete_prompt_menu"
    else:
        back_callback = "admin_scenes"
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_scene_plans_admin_list(plans: List, group_id: int, action: str = "edit") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for plan in plans:
        if action == "edit":
            callback = f"scene_admin_edit_plan_{plan.id}"
        elif action == "delete":
            callback = f"scene_admin_delete_plan_{plan.id}"
        else:
            callback = f"scene_admin_view_plan_{plan.id}"
        
        builder.row(InlineKeyboardButton(text=plan.name, callback_data=callback))
    
    if action == "edit":
        back_callback = "scene_edit_prompt_menu"
    elif action == "delete":
        back_callback = "scene_delete_prompt_menu"
    else:
        back_callback = "admin_scenes"
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()



def get_user_management_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="user_search"))
    builder.row(InlineKeyboardButton(text="🚫 Заблокированные пользователи", callback_data="user_banned_list"))
    builder.row(InlineKeyboardButton(text="👥 Все пользователи (последние 20)", callback_data="user_all_list"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_user_detail_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
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
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data=f"balance_add_{user_id}"),
        InlineKeyboardButton(text="➖ Убавить", callback_data=f"balance_subtract_{user_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"user_view_{user_id}"))
    return builder.as_markup()


def get_user_list_keyboard(users: List, offset: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for user in users:
        status = "🚫" if user.is_banned else "✅"
        username = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        builder.row(InlineKeyboardButton(
            text=f"{status} {username} ({user.balance} кр.)",
            callback_data=f"user_view_{user.telegram_id}"
        ))
    
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




def get_confirmation_keyboard_photo(cost: int, back_to: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, списать", callback_data=f"photo_confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"photo_back_{back_to}")
    )
    return builder.as_markup()


def get_model_type_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👁 Просмотр всех типов", callback_data="model_type_view_all"))
    builder.row(InlineKeyboardButton(text="➕ Добавить тип", callback_data="model_type_add"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить тип", callback_data="model_type_delete_menu"))
    builder.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return builder.as_markup()


def get_model_types_list(model_types: List, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for mt in model_types:
        if action == "edit":
            callback = f"model_type_edit_{mt.id}"
            text = f"✏️ {mt.name}"
        elif action == "delete":
            callback = f"model_type_delete_{mt.id}"
            text = f"🗑 {mt.name}"
        else:
            callback = f"model_type_view_{mt.id}"
            text = f"{mt.name}"
        
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_model_types"))
    return builder.as_markup()

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


# ===== MODEL CATEGORY KEYBOARDS =====
def get_model_category_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить категорию", callback_data="model_cat_add_category"))
    builder.row(InlineKeyboardButton(text="➕ Добавить подкатегорию", callback_data="model_cat_add_subcategory"))
    builder.row(InlineKeyboardButton(text="➕ Добавить элемент", callback_data="model_cat_add_item"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="model_cat_edit_menu"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="model_cat_delete_menu"))
    builder.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return builder.as_markup()


def get_model_categories_list(categories: List, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for cat in categories:
        if action == "add_subcat":
            callback = f"model_cat_add_subcat_{cat.id}"
        elif action == "add_item":
            callback = f"model_cat_add_item_{cat.id}"
        elif action == "edit":
            callback = f"model_cat_edit_{cat.id}"
        elif action == "delete":
            callback = f"model_cat_delete_{cat.id}"
        else:
            callback = f"model_cat_view_{cat.id}"
        
        builder.row(InlineKeyboardButton(text=cat.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_model_categories"))
    return builder.as_markup()


def get_model_subcategories_list(subcategories: List, category_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for subcat in subcategories:
        if action == "add_item":
            callback = f"model_subcat_add_item_{category_id}_{subcat.id}"
        elif action == "edit":
            callback = f"model_subcat_edit_{category_id}_{subcat.id}"
        elif action == "delete":
            callback = f"model_subcat_delete_{category_id}_{subcat.id}"
        else:
            callback = f"model_subcat_view_{category_id}_{subcat.id}"
        
        builder.row(InlineKeyboardButton(text=subcat.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="model_cat_add_item" if action == "add_item" else "admin_model_categories"))
    return builder.as_markup()


def get_model_items_list(items: List, category_id: int, subcategory_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for item in items:
        if action == "edit":
            callback = f"model_item_edit_{item.id}"
        elif action == "delete":
            callback = f"model_item_delete_{item.id}"
        else:
            callback = f"model_item_view_{item.id}"
        
        builder.row(InlineKeyboardButton(text=item.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_model_categories"))
    return builder.as_markup()


# ===== SCENE CATEGORY KEYBOARDS =====
def get_scene_category_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить категорию", callback_data="scene_cat_add_category"))
    builder.row(InlineKeyboardButton(text="➕ Добавить подкатегорию", callback_data="scene_cat_add_subcategory"))
    builder.row(InlineKeyboardButton(text="➕ Добавить элемент", callback_data="scene_cat_add_item"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="scene_cat_edit_menu"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="scene_cat_delete_menu"))
    builder.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return builder.as_markup()


def get_scene_categories_list(categories: List, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for cat in categories:
        if action == "add_subcat":
            callback = f"scene_cat_add_subcat_{cat.id}"
        elif action == "add_item":
            callback = f"scene_cat_add_item_{cat.id}"
        elif action == "edit":
            callback = f"scene_cat_edit_{cat.id}"
        elif action == "delete":
            callback = f"scene_cat_delete_{cat.id}"
        else:
            callback = f"scene_cat_view_{cat.id}"
        
        builder.row(InlineKeyboardButton(text=cat.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_scenes"))
    return builder.as_markup()


def get_scene_subcategories_list(subcategories: List, category_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for subcat in subcategories:
        if action == "add_item":
            callback = f"scene_subcat_add_item_{category_id}_{subcat.id}"
        elif action == "edit":
            callback = f"scene_subcat_edit_{category_id}_{subcat.id}"
        elif action == "delete":
            callback = f"scene_subcat_delete_{category_id}_{subcat.id}"
        else:
            callback = f"scene_subcat_view_{category_id}_{subcat.id}"
        
        builder.row(InlineKeyboardButton(text=subcat.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="scene_cat_add_item" if action == "add_item" else "admin_scenes"))
    return builder.as_markup()


def get_scene_items_list(items: List, category_id: int, subcategory_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for item in items:
        if action == "edit":
            callback = f"scene_item_edit_{item.id}"
        elif action == "delete":
            callback = f"scene_item_delete_{item.id}"
        else:
            callback = f"scene_item_view_{item.id}"
        
        builder.row(InlineKeyboardButton(text=item.name, callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_scenes"))
    return builder.as_markup()


# ===== COMMON KEYBOARDS =====
def get_cancel_keyboard(back_to: str = "admin_back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=back_to))
    return builder.as_markup()


def get_confirm_delete_keyboard(item_type: str, item_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{item_type}_{item_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")
    )
    return builder.as_markup()


def get_admin_back_keyboard(back_to: str = "admin_back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_to))
    return builder.as_markup()


# Eski funksiyalarni ham qoldiring (boshqa handlerlar uchun)
def get_pose_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить группу", callback_data="pose_add_main_group"))
    builder.row(InlineKeyboardButton(text="➕ Добавить подгруппу", callback_data="pose_add_main_subgroup"))
    builder.row(InlineKeyboardButton(text="➕ Добавить промпт", callback_data="pose_add_main_prompt"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="pose_edit_main_menu"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="pose_delete_main_menu"))
    builder.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return builder.as_markup()


def get_pose_groups_admin_list(groups: List, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for group in groups:
        if action == "add_subgroup":
            callback = f"pose_admin_add_subgroup_group_{group.id}"
        elif action == "add_prompt":
            callback = f"pose_admin_add_prompt_group_{group.id}"
        elif action == "edit":
            callback = f"pose_admin_edit_group_{group.id}"
        elif action == "delete":
            callback = f"pose_admin_delete_group_{group.id}"
        else:
            callback = f"pose_admin_view_group_{group.id}"
        
        builder.row(InlineKeyboardButton(text=f"{group.name}", callback_data=callback))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_poses"))
    return builder.as_markup()


def get_pose_subgroups_admin_list(subgroups: List, group_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for subgroup in subgroups:
        if action == "add_prompt":
            callback = f"pose_admin_add_prompt_subgroup_{group_id}_{subgroup.id}"
        elif action == "edit":
            callback = f"pose_admin_edit_subgroup_{group_id}_{subgroup.id}"
        elif action == "delete":
            callback = f"pose_admin_delete_subgroup_{group_id}_{subgroup.id}"
        else:
            callback = f"pose_admin_view_subgroup_{group_id}_{subgroup.id}"
        
        builder.row(InlineKeyboardButton(text=f"{subgroup.name}", callback_data=callback))
    
    if action == "edit":
        back_callback = "pose_edit_main_menu"
    elif action == "delete":
        back_callback = "pose_delete_main_menu"
    else:
        back_callback = "admin_poses"
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_pose_prompts_admin_list(prompts: List, group_id: int, subgroup_id: int, action: str = "view") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for prompt in prompts:
        if action == "edit":
            callback = f"pose_admin_edit_prompt_{prompt.id}"
        elif action == "delete":
            callback = f"pose_admin_delete_prompt_{prompt.id}"
        else:
            callback = f"pose_admin_view_prompt_{prompt.id}"
        
        builder.row(InlineKeyboardButton(text=f"{prompt.name}", callback_data=callback))
    
    if action == "edit":
        back_callback = "pose_edit_main_menu"
    elif action == "delete":
        back_callback = "pose_delete_main_menu"
    else:
        back_callback = "admin_poses"
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_admin_video_main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👁 Просмотр сценариев", callback_data="vidsc_view"))
    b.row(InlineKeyboardButton(text="➕ Добавить сценарий", callback_data="vidsc_add"))
    b.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="vidsc_edit_menu"))
    b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data="vidsc_delete_menu"))
    b.row(InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_back"))
    return b.as_markup()

def get_video_scenarios_list(scenarios: List, action: str = "view") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in scenarios:
        text = f"{'✅' if s.is_active else '🚫'} {s.name} • #{s.order_index}"
        if action == "edit":
            cb = f"vidsc_pick_{s.id}"
        elif action == "delete":
            cb = f"vidsc_delete_{s.id}"
        else:
            cb = f"vidsc_view_{s.id}"
        b.row(InlineKeyboardButton(text=text, callback_data=cb))

    back = "admin_video_scenarios"
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back))
    return b.as_markup()

def kb_video_empty_state() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="➕ Добавить сценарий", callback_data="vidsc_add"))
    b.row(InlineKeyboardButton(text="◀️ В меню сценариев", callback_data="admin_video_scenarios"))
    return b.as_markup()

def get_video_scenario_detail_keyboard(scenario_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="vidsc_view"))
    return b.as_markup()

def get_video_scenario_edit_menu(scenario_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✏️ Имя", callback_data=f"vidsc_edit_name_{scenario_id}"))
    b.row(InlineKeyboardButton(text="📝 Промпт", callback_data=f"vidsc_edit_prompt_{scenario_id}"))
    b.row(InlineKeyboardButton(text="🔢 Порядок", callback_data=f"vidsc_edit_order_{scenario_id}"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"vidsc_view_{scenario_id}"))
    return b.as_markup()

def get_confirm_delete_keyboard_video(scenario_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"vidsc_delete_confirm_{scenario_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"vidsc_view_{scenario_id}")
    )
    return b.as_markup()

def kb_add_flow_back_cancel() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="vidsc_add_cancel"))
    return b.as_markup()

def kb_back_to_admin_video_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ В меню сценариев", callback_data="admin_video_scenarios"))
    return b.as_markup()

def kb_back_to_edit_menu(scenario_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"vidsc_view_{scenario_id}"))
    return b.as_markup()