# handlers/photo.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from states import PhotoStates
from keyboards import (
    get_photo_menu, get_back_button_photo, get_confirmation_keyboard_photo,
    get_repeat_button, get_back_to_generation, get_generation_menu
)
from database import async_session_maker
from database.repositories import SceneRepository, UserRepository, PoseRepository
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
    await safe_edit_text(callback, "📸 <b>Фото</b>\n\nВыберите режим обработки фото:", reply_markup=get_photo_menu(), parse_mode="HTML")


@router.callback_query(F.data == "photo_scene")
async def photo_scene_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="scene_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button_photo("photo_scene"), parse_mode="HTML")


@router.callback_query(F.data == "photo_pose")
async def photo_pose_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="pose_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button_photo("photo_pose"), parse_mode="HTML")


@router.callback_query(F.data == "photo_custom")
async def photo_custom_scenario(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="custom")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button_photo("photo_custom"), parse_mode="HTML")


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
        async with async_session_maker() as session:
            repo = SceneRepository(session)
            groups = await repo.get_all_groups()

        kb = InlineKeyboardBuilder()
        for group in groups:
            kb.row(InlineKeyboardButton(text=group.name, callback_data=f"photo_user_scene_group_{group.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))

        await message.answer("Выберите локацию:", reply_markup=kb.as_markup())
        await state.set_state(PhotoStates.selecting_group)

    elif mode == "pose_change":
        async with async_session_maker() as session:
            repo = PoseRepository(session)
            groups = await repo.get_all_groups()

        kb = InlineKeyboardBuilder()
        for group in groups:
            kb.row(InlineKeyboardButton(text=group.name, callback_data=f"photo_user_pose_group_{group.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))

        await message.answer("Выберите группу поз:", reply_markup=kb.as_markup())
        await state.set_state(PhotoStates.selecting_group)

    elif mode == "custom":
        await message.answer("Введите свой промпт:", reply_markup=get_back_button_photo("photo_received"))
        await state.set_state(PhotoStates.entering_custom_prompt)


@router.callback_query(PhotoStates.selecting_group, F.data.startswith("photo_user_scene_group_"))
async def select_scene_group_user(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.replace("photo_user_scene_group_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        group = await repo.get_group(group_id)
        plans = await repo.get_plans_by_group(group_id)

    if not plans:
        await safe_edit_text(callback, "❌ В этой локации нет планов!", reply_markup=get_back_button_photo("photo_received"))
        return

    kb = InlineKeyboardBuilder()
    for plan in plans:
        kb.row(InlineKeyboardButton(text=plan.name, callback_data=f"photo_user_scene_plan_{plan.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_group"))

    await safe_edit_text(
        callback,
        f"<b>{group.name}</b>\n\nВыберите план:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_plan)
    await state.update_data(selected_group=group_id)


@router.callback_query(PhotoStates.selecting_plan, F.data.startswith("photo_user_scene_plan_"))
async def apply_scene_plan_user(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.replace("photo_user_scene_plan_", ""))
    await callback.answer("⏳ Генерация...")

    data = await state.get_data()
    photo_url = data["photo_url"]

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        plan = await repo.get_plan(plan_id)
        user_repo = UserRepository(session)

        cost = config_loader.pricing["photo"]["scene_change"]
        if not await user_repo.check_balance(callback.from_user.id, cost):
            await safe_edit_text(callback, "❌ Недостаточно кредитов.", reply_markup=get_back_to_generation())
            await state.clear()
            return

        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    await safe_edit_text(callback, "⏳ Генерация...")

    try:
        print("PLAN PROMPT:", plan.prompt)
        result = await kie_service.change_scene(photo_url, plan.prompt)
        if "image" in result:
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], "result.jpg"),
                caption=f"✅ {plan.name}"
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
        "type": "photo", "photo_url": photo_url, "mode": "scene_change",
        "plan_id": plan_id, "cost": cost
    })


@router.callback_query(PhotoStates.selecting_group, F.data.startswith("photo_user_pose_group_"))
async def select_pose_group_user(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.replace("photo_user_pose_group_", ""))
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
        kb.row(InlineKeyboardButton(text=subgroup.name, callback_data=f"photo_user_pose_subgroup_{group_id}_{subgroup.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_group"))

    await safe_edit_text(
        callback,
        f"<b>{group.name}</b>\n\nВыберите подгруппу:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_subgroup)
    await state.update_data(selected_group=group_id)


@router.callback_query(PhotoStates.selecting_subgroup, F.data.startswith("photo_user_pose_subgroup_"))
async def select_pose_subgroup_user(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.replace("photo_user_pose_subgroup_", "").split("_")
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
        kb.row(InlineKeyboardButton(text=prompt.name, callback_data=f"photo_user_pose_prompt_{prompt.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"photo_user_pose_group_{group_id}"))

    await safe_edit_text(
        callback,
        f"<b>{subgroup.name}</b>\n\nВыберите промпт:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.selecting_prompt)
    await state.update_data(selected_subgroup=subgroup_id)


@router.callback_query(PhotoStates.selecting_prompt, F.data.startswith("photo_user_pose_prompt_"))
async def apply_pose_prompt_user(callback: CallbackQuery, state: FSMContext):
    prompt_id = int(callback.data.replace("photo_user_pose_prompt_", ""))
    await callback.answer("⏳ Генерация...")

    data = await state.get_data()
    photo_url = data["photo_url"]

    async with async_session_maker() as session:
        repo = PoseRepository(session)
        prompt = await repo.get_prompt(prompt_id)
        user_repo = UserRepository(session)

        cost = config_loader.pricing["photo"]["pose_change"]
        if not await user_repo.check_balance(callback.from_user.id, cost):
            await safe_edit_text(callback, "❌ Недостаточно кредитов.", reply_markup=get_back_to_generation())
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
        "type": "photo", "photo_url": photo_url, "mode": "pose_change",
        "prompt_id": prompt_id, "cost": cost
    })


@router.message(PhotoStates.entering_custom_prompt, F.text)
async def custom_prompt_received(message: Message, state: FSMContext):
    prompt = await translator_service.translate_ru_to_en(message.text)
    cost = config_loader.pricing["photo"]["custom_scenario"]
    await state.update_data(prompt=prompt, cost=cost)

    async with async_session_maker() as session:
        repo = UserRepository(session)
        if not await repo.check_balance(message.from_user.id, cost):
            await message.answer("❌ Недостаточно кредитов.", reply_markup=get_back_to_generation())
            await state.clear()
            return

    await message.answer(
        f"Промпт: {prompt}\n\nСписать {cost} кр.?",
        reply_markup=get_confirmation_keyboard_photo(cost, "entering_custom_prompt")
    )
    await state.set_state(PhotoStates.confirming)


@router.callback_query(F.data.startswith("photo_confirm_"))
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


@router.callback_query(F.data.startswith("photo_back_"))
async def back_navigation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    step = callback.data.replace("photo_back_", "")

    if step == "gen_photo":
        await state.clear()
        await safe_edit_text(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
        return

    if step in ["photo_scene", "photo_pose", "photo_custom"]:
        await state.clear()
        await safe_edit_text(callback, "📸 <b>Фото</b>\n\nВыберите режим:", reply_markup=get_photo_menu(), parse_mode="HTML")
        return

    if step == "photo_received":
        data = await state.get_data()
        mode = data.get("mode", "custom")
        await state.set_state(PhotoStates.waiting_for_photo)
        text = {
            "scene_change": "📸 Отправьте ОДНО фото для смены сцены.",
            "pose_change": "📸 Отправьте ОДНО фото для смены позы.",
            "custom": "📸 Отправьте ОДНО фото для обработки."
        }[mode]
        await safe_edit_text(callback, text, reply_markup=get_back_button_photo(step), parse_mode="HTML")
        return

    if step == "selecting_group":
        await state.set_state(PhotoStates.waiting_for_photo)
        data = await state.get_data()
        mode = data.get("mode")
        text = "📸 Отправьте ОДНО фото для смены сцены." if mode == "scene_change" else "📸 Отправьте ОДНО фото для смены позы."
        await safe_edit_text(callback, text, reply_markup=get_back_button_photo("photo_scene" if mode == "scene_change" else "photo_pose"), parse_mode="HTML")
        return