from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from handlers.start import send_bot_message
from states import PhotoStates
from keyboards import (
    get_back_to_generation_with_buy, get_generation_menu, get_photo_menu, get_back_button_photo, get_confirmation_keyboard_photo,
    get_repeat_button, get_back_to_generation
)
from database import async_session_maker
from database.repositories import SceneCategoryRepository, UserRepository, PoseRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
import logging

from utils.photo import get_photo_url_from_message

logger = logging.getLogger(__name__)
router = Router()


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
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


@router.callback_query(F.data == "gen_photo")
async def photo_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await send_bot_message(callback, "photo", get_photo_menu())


@router.callback_query(F.data == "photo_scene")
async def photo_scene_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="scene_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button_photo("gen_photo"), parse_mode="HTML")


@router.callback_query(F.data == "photo_pose")
async def photo_pose_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="pose_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button_photo("gen_photo"), parse_mode="HTML")


@router.callback_query(F.data == "photo_custom")
async def photo_custom_scenario(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="custom")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button_photo("gen_photo"), parse_mode="HTML")


# ===== PHOTO RECEIVED =====
@router.message(PhotoStates.waiting_for_photo, F.photo | F.document)
async def photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        await message.answer("❌ Пожалуйста, отправьте только ОДНО фото.", reply_markup=get_back_button_photo("gen_photo"))
        return

    try:
        photo_url = await get_photo_url_from_message(message)
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await message.answer("❌ Ошибка при обработке фото.", reply_markup=get_back_button_photo("gen_photo"))
        return

    data = await state.get_data()
    mode = data["mode"]
    await state.update_data(photo_url=photo_url)

    if mode == "scene_change":
        # YANGI: 3-darajali struktura
        async with async_session_maker() as session:
            repo = SceneCategoryRepository(session)
            categories = await repo.get_all_categories()

        kb = InlineKeyboardBuilder()
        for category in categories:
            kb.row(InlineKeyboardButton(text=category.name, callback_data=f"photo_scene_cat_{category.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_waiting_for_photo"))

        await message.answer("Выберите категорию:", reply_markup=kb.as_markup())
        await state.set_state(PhotoStates.selecting_scene_category)

    elif mode == "pose_change":
        async with async_session_maker() as session:
            repo = PoseRepository(session)
            groups = await repo.get_all_groups()

        kb = InlineKeyboardBuilder()
        for group in groups:
            kb.row(InlineKeyboardButton(text=group.name, callback_data=f"photo_pose_group_{group.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_waiting_for_photo"))

        await message.answer("Выберите группу поз:", reply_markup=kb.as_markup())
        await state.set_state(PhotoStates.selecting_pose_group)

    elif mode == "custom":
        await message.answer("Введите свой промпт:", reply_markup=get_back_button_photo("waiting_for_photo"))
        await state.set_state(PhotoStates.entering_custom_prompt)


# ===== SCENE: SELECT CATEGORY =====
@router.callback_query(PhotoStates.selecting_scene_category, F.data.startswith("photo_scene_cat_"))
async def select_scene_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.replace("photo_scene_cat_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneCategoryRepository(session)
        category = await repo.get_category(category_id)
        subcategories = await repo.get_subcategories_by_category(category_id)

    if not subcategories:
        await safe_edit_text(callback, "❌ В этой категории нет подкатегорий!", reply_markup=get_back_button_photo("photo_received"))
        return

    kb = InlineKeyboardBuilder()
    for subcat in subcategories:
        kb.row(InlineKeyboardButton(text=subcat.name, callback_data=f"photo_scene_subcat_{category_id}_{subcat.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_scene_category"))

    await safe_edit_text(
        callback,
        f"<b>{category.name}</b>\n\nВыберите подкатегорию:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_scene_subcategory)
    await state.update_data(scene_category_id=category_id)


# ===== SCENE: SELECT SUBCATEGORY =====
@router.callback_query(PhotoStates.selecting_scene_subcategory, F.data.startswith("photo_scene_subcat_"))
async def select_scene_subcategory(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.replace("photo_scene_subcat_", "").split("_")
    category_id = int(parts[0])
    subcategory_id = int(parts[1])
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneCategoryRepository(session)
        subcategory = await repo.get_subcategory(subcategory_id)
        items = await repo.get_items_by_subcategory(subcategory_id)

    if not items:
        await safe_edit_text(callback, "❌ В этой подкатегории нет элементов!", reply_markup=get_back_button_photo("photo_received"))
        return

    kb = InlineKeyboardBuilder()
    for item in items:
        kb.row(InlineKeyboardButton(text=item.name, callback_data=f"photo_scene_item_{item.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"photo_scene_cat_{category_id}"))

    await safe_edit_text(
        callback,
        f"<b>{subcategory.name}</b>\n\nВыберите сцену:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_scene_item)
    await state.update_data(scene_subcategory_id=subcategory_id)


# ===== SCENE: APPLY ITEM =====
@router.callback_query(PhotoStates.selecting_scene_item, F.data.startswith("photo_scene_item_"))
async def apply_scene_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("photo_scene_item_", ""))
    await callback.answer("⏳ Генерация...")

    data = await state.get_data()
    photo_url = data["photo_url"]

    async with async_session_maker() as session:
        repo = SceneCategoryRepository(session)
        item = await repo.get_item(item_id)
        user_repo = UserRepository(session)

        cost = config_loader.pricing["photo"]["scene_change"]
        if not await user_repo.check_balance(callback.from_user.id, cost):
            await safe_edit_text(callback, "❌ Недостаточно кредитов.", reply_markup=get_back_to_generation_with_buy())
            await state.clear()
            return

        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    await safe_edit_text(callback, "⏳ Генерация...")

    try:
        result = await kie_service.change_scene(photo_url, item.prompt)
        if "image" in result:
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], "result.jpg"),
                caption=f"✅ {item.name}"
            )
        await callback.message.answer(
            f"✅ Готово!\n\nПотрачено: {cost} кр.\nБаланс: {user.balance} кр.",
            reply_markup=get_repeat_button()
        )
    except Exception as e:
        logger.error(f"Scene error: {e}")
        await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer("❌ Ошибка генерации. Кредиты возвращены.")

    await state.clear()
    await state.update_data(last_generation={
        "type": "photo",
        "mode": "scene_change",
        "photo_url": photo_url,
        "item_id": item.id,                # 3-darajali ITEM ID
        "cost": cost
    })


# ===== POSE: SELECT GROUP =====
@router.callback_query(PhotoStates.selecting_pose_group, F.data.startswith("photo_pose_group_"))
async def select_pose_group(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.replace("photo_pose_group_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = PoseRepository(session)
        group = await repo.get_group(group_id)
        subgroups = await repo.get_subgroups_by_group(group_id)

    if not subgroups:
        await safe_edit_text(callback, "❌ В этой группе нет подгрупп!", reply_markup=get_back_button_photo("photo_received"))
        return

    kb = InlineKeyboardBuilder()
    for subgroup in subgroups:
        kb.row(InlineKeyboardButton(text=subgroup.name, callback_data=f"photo_pose_subgroup_{group_id}_{subgroup.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_pose_group"))

    await safe_edit_text(
        callback,
        f"<b>{group.name}</b>\n\nВыберите подгруппу:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_pose_subgroup)
    await state.update_data(pose_group_id=group_id)


# ===== POSE: SELECT SUBGROUP =====
@router.callback_query(PhotoStates.selecting_pose_subgroup, F.data.startswith("photo_pose_subgroup_"))
async def select_pose_subgroup(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.replace("photo_pose_subgroup_", "").split("_")
    group_id = int(parts[0])
    subgroup_id = int(parts[1])
    await callback.answer()

    async with async_session_maker() as session:
        repo = PoseRepository(session)
        subgroup = await repo.get_subgroup(subgroup_id)
        prompts = await repo.get_prompts_by_subgroup(subgroup_id)

    if not prompts:
        await safe_edit_text(callback, "❌ В этой подгруппе нет промптов!", reply_markup=get_back_button_photo("photo_received"))
        return

    kb = InlineKeyboardBuilder()
    for prompt in prompts:
        kb.row(InlineKeyboardButton(text=prompt.name, callback_data=f"photo_pose_prompt_{prompt.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"photo_pose_group_{group_id}"))

    await safe_edit_text(
        callback,
        f"<b>{subgroup.name}</b>\n\nВыберите промпт:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_pose_prompt)
    await state.update_data(pose_subgroup_id=subgroup_id)


# ===== POSE: APPLY PROMPT =====
@router.callback_query(PhotoStates.selecting_pose_prompt, F.data.startswith("photo_pose_prompt_"))
async def apply_pose_prompt(callback: CallbackQuery, state: FSMContext):
    prompt_id = int(callback.data.replace("photo_pose_prompt_", ""))
    await callback.answer("⏳ Генерация...")

    data = await state.get_data()
    photo_url = data["photo_url"]

    async with async_session_maker() as session:
        repo = PoseRepository(session)
        prompt = await repo.get_prompt(prompt_id)
        user_repo = UserRepository(session)

        cost = config_loader.pricing["photo"]["pose_change"]
        if not await user_repo.check_balance(callback.from_user.id, cost):
            await safe_edit_text(callback, "❌ Недостаточно кредитов.", reply_markup=get_back_to_generation_with_buy())
            await state.clear()
            return

        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    await safe_edit_text(callback, "⏳ Генерация...")

    try:
        result = await kie_service.change_pose(photo_url, prompt.prompt)
        if "image" in result:
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], "result.jpg"),
                caption=f"✅ {prompt.name}"
            )
        await callback.message.answer(
            f"✅ Готово!\n\nПотрачено: {cost} кр.\nБаланс: {user.balance} кр.",
            reply_markup=get_repeat_button()
        )
    except Exception as e:
        logger.error(f"Pose error: {e}")
        await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer("❌ Ошибка генерации. Кредиты возвращены.")

    await state.clear()
    await state.update_data(last_generation={
        "type": "photo",
        "mode": "pose_change",
        "photo_url": photo_url,
        "prompt_id": prompt.id,            
        "cost": cost
    })


@router.message(PhotoStates.entering_custom_prompt, F.text)
async def custom_prompt_received(message: Message, state: FSMContext):
    prompt = await translator_service.translate_ru_to_en(message.text)
    cost = config_loader.pricing["photo"]["custom_scenario"]
    await state.update_data(prompt=prompt, cost=cost)

    async with async_session_maker() as session:
        repo = UserRepository(session)
        if not await repo.check_balance(message.from_user.id, cost):
            await message.answer("❌ Недостаточно кредитов.", reply_markup=get_back_to_generation_with_buy())
            await state.clear()
            return

    await message.answer(
        f"Промпт: {prompt}\n\nСписать {cost} кр.?",
        reply_markup=get_confirmation_keyboard_photo(cost, "entering_custom_prompt")
    )
    await state.set_state(PhotoStates.confirming)


@router.callback_query(PhotoStates.confirming, F.data.startswith("confirm_"))
async def confirm_custom(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_url = data["photo_url"]
    prompt = data["prompt"]
    cost = data["cost"]

    async with async_session_maker() as session:
        repo = UserRepository(session)
        await repo.update_balance(callback.from_user.id, -cost)
        user = await repo.get_user_by_telegram_id(callback.from_user.id)

    await safe_edit_text(callback, "⏳ Генерация...")

    try:
        result = await kie_service.custom_generation(photo_url, prompt)
        if "image" in result:
            await callback.message.answer_photo(BufferedInputFile(result["image"], "custom.jpg"))
        await callback.message.answer(
            f"✅ Готово!\n\nПотрачено: {cost} кр.\nБаланс: {user.balance} кр.",
            reply_markup=get_repeat_button()
        )
    except Exception as e:
        await repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer("❌ Ошибка. Кредиты возвращены.")

    await state.clear()
    await state.update_data(last_generation={
        "type": "photo",
        "mode": "custom",
        "photo_url": photo_url,
        "prompt": prompt,                  # Tarjima qilingan prompt
        "cost": cost
    })
    


# ===== BACK NAVIGATION =====
@router.callback_query(F.data.startswith("photo_back_"))
async def back_navigation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    step = callback.data.replace("photo_back_", "")

    if step == "gen_photo":
        await state.clear()
        await safe_edit_text(callback, 
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )

    if step == "waiting_for_photo":
        data = await state.get_data()
        mode = data.get("mode", "custom")
        await state.set_state(PhotoStates.waiting_for_photo)
        text = {
            "scene_change": "📸 Отправьте ОДНО фото для смены сцены.",
            "pose_change": "📸 Отправьте ОДНО фото для смены позы.",
            "custom": "📸 Отправьте ОДНО фото для обработки."
        }[mode]
        await safe_edit_text(callback, text, reply_markup=get_back_button_photo("gen_photo"), parse_mode="HTML")
        return

    if step == "selecting_scene_category":
        await photo_received(callback.message, state)
        return

    if step == "selecting_pose_group":
        await photo_received(callback.message, state)
        return