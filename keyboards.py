from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from database.repositories import UserRepository


def get_back_button_normalize(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data=f"norm_back_{current_step}"
    ))
    return builder.as_markup()


def get_back_button_photo(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data=f"photo_back_{current_step}"
    ))
    return builder.as_markup()


def get_back_button_video(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data=f"video_back_{current_step}"
    ))
    return builder.as_markup()


def get_back_button_product_card(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data=f"pc_back_{current_step}"
    ))
    return builder.as_markup()



def get_back_to_generation():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню генерации", callback_data="back_to_generations")]
    ])


def get_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🪄 Генерация", callback_data="main_generation"))
    builder.row(InlineKeyboardButton(text="👤 Мой кабинет", callback_data="main_cabinet"))
    return builder.as_markup()


def get_generation_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📦 Готовая карточка товара", callback_data="gen_product_card"))
    builder.row(InlineKeyboardButton(text="👗 Нормализация фото", callback_data="gen_normalize"))
    builder.row(InlineKeyboardButton(text="🎬 Видео", callback_data="gen_video"))
    builder.row(InlineKeyboardButton(text="📸 Фото", callback_data="gen_photo"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    return builder.as_markup()



def get_normalize_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🧍 Есть своя фотомодель", callback_data="norm_own_model"))
    builder.row(InlineKeyboardButton(text="👗 Новая фотомодель", callback_data="norm_new_model"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="norm_back_gen_normalize"))
    return builder.as_markup()


def get_model_types(models: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for model in models:
        builder.row(InlineKeyboardButton(
            text=model["name"], 
            callback_data=f"model_{model['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="norm_back_norm_new_model"))
    return builder.as_markup()


def get_confirmation_keyboard_normalize(cost: int, back_data: str = "confirming") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"norm_back_{back_data}")
    )
    return builder.as_markup()



def get_video_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚖️ Баланс — Grok", callback_data="video_balance"))
    builder.row(InlineKeyboardButton(text="⭐ Про 6 сек — hailuo 768p", callback_data="video_pro6"))
    builder.row(InlineKeyboardButton(text="⭐⭐ Про 10 сек — hailuo 768p", callback_data="video_pro10"))
    builder.row(InlineKeyboardButton(text="⭐⭐⭐ Супер Про 6 сек — hailuo 1080p", callback_data="video_super6"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="video_back_gen_video"))
    return builder.as_markup()


def get_video_scenarios(scenarios: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for scenario in scenarios[:9]:
        builder.row(InlineKeyboardButton(
            text=scenario["name"], 
            callback_data=f"video_scenario_{scenario['id']}"
        ))
    builder.row(InlineKeyboardButton(text="✏️ Свой промпт", callback_data="video_custom_prompt"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="video_back_waiting_for_photo"))
    return builder.as_markup()


def get_confirmation_keyboard_video(cost: int, back_data: str = "confirming") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"video_back_{back_data}")
    )
    return builder.as_markup()



def get_photo_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌆 Смена сцены", callback_data="photo_scene"))
    builder.row(InlineKeyboardButton(text="🤸 Смена позы", callback_data="photo_pose"))
    builder.row(InlineKeyboardButton(text="✨ Свой сценарий", callback_data="photo_custom"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_gen_photo"))
    return builder.as_markup()


def get_scene_groups(groups: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.row(InlineKeyboardButton(text=group["name"], callback_data=f"scene_group_{group['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_scene_groups"))
    return builder.as_markup()


def get_scenes_in_group(scenes: List[dict], group_id: str) -> InlineKeyboardMarkup:
    keyboard = []
    for scene in scenes:
        keyboard.append([InlineKeyboardButton(
            text=scene["name"], 
            callback_data=f"scene_{scene['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="✅ Все сцены группы", 
        callback_data=f"scene_all_{group_id}"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data="photo_back_selecting_scene_group"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_pose_groups(groups: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.row(InlineKeyboardButton(
            text=group["name"], 
            callback_data=f"pose_group_{group['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_group"))
    return builder.as_markup()


def get_poses_in_group(poses: List[dict], group_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for pose in poses:
        builder.row(InlineKeyboardButton(
            text=pose["name"],
            callback_data=f"pose_{pose['id']}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="✅ Все позы группы", 
        callback_data=f"pose_all_{group_id}"
    ))
    
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data="photo_back_selecting_group_pose"
    ))
    
    return builder.as_markup()

def get_scene_groups_pc(groups: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.row(InlineKeyboardButton(
            text=group["name"], 
            callback_data=f"pc_scene_group_{group['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_groups"))
    return builder.as_markup()


def get_scenes_in_group_pc(scenes: List[dict], group_id: str) -> InlineKeyboardMarkup:
    keyboard = []
    for scene in scenes:
        keyboard.append([InlineKeyboardButton(
            text=scene["name"], 
            callback_data=f"pc_scene_{scene['id']}" 
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="✅ Все сцены группы", 
        callback_data=f"pc_scene_all_{group_id}"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data="pc_back_selecting_scene_group"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard_photo(cost: int, back_data: str = "confirming") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"photo_back_{back_data}")
    )
    return builder.as_markup()


def get_product_card_plans() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
    builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_to_root"))
    return builder.as_markup()


def get_scene_plans() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📍 Дальний", callback_data="plan_far"),
        InlineKeyboardButton(text="📍 Средний", callback_data="plan_medium")
    )
    builder.row(InlineKeyboardButton(text="📍 Крупный", callback_data="plan_close"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene"))
    return builder.as_markup()


def get_confirmation_keyboard_product_card(cost: int, back_data: str = "gen_product_card") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"✅ Подтвердить ({cost} кредитов)", 
        callback_data="confirm_product_card"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", 
        callback_data=f"pc_back_{back_data}"
    ))
    return builder.as_markup()


def get_cabinet_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Баланс / Пополнение", callback_data="cabinet_balance"))
    builder.row(InlineKeyboardButton(text="❓ Справка / FAQ", callback_data="cabinet_faq"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    return builder.as_markup()


def get_back_to_cabinet() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В кабинет", callback_data="main_cabinet"))
    return builder.as_markup()


def get_payment_packages(packages: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for package in packages:
        bonus = f" ({package.get('bonus')})" if package.get('bonus') else ""
        text = f"{package['label']} — {package['price']} ₽{bonus}"
        builder.row(InlineKeyboardButton(
            text=text, 
            callback_data=f"buy_{package['credits']}_{package['price']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ В кабинет", callback_data="main_cabinet"))
    return builder.as_markup()


def get_repeat_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Повторить", callback_data="repeat_generation"))
    builder.row(InlineKeyboardButton(text="🔙 В меню генерации", callback_data="back_to_generations"))
    return builder.as_markup()



def get_dynamic_back_button(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{current_step}"))
    return builder.as_markup()


def get_confirmation_keyboard(cost: int, back_data: str = "confirming") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_{back_data}")
    )
    return builder.as_markup()