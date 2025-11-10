from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from states import ProductCardStates
from keyboards import (get_product_card_plans, get_scene_plans, get_scene_groups,
                       get_scenes_in_group, get_confirmation_keyboard, 
                       get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import UserRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


async def safe_edit_or_skip(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
        else:
            raise


@router.callback_query(F.data == "gen_product_card")
async def product_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    # Navigation stack boshlash
    await state.update_data(nav_stack=["gen_product_card"])
    await state.set_state(ProductCardStates.waiting_for_photo)
    await callback.message.edit_text(
        "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.\n\nЯ создам серию изображений по разным сценам.", 
        reply_markup=get_back_button("gen_product_card")
    )


@router.message(ProductCardStates.waiting_for_photo, F.photo)
async def product_card_photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        nav_stack = data.get("nav_stack", [])
        await message.answer("❌ Для карточки нужно ровно ОДНО фото (не альбом).", reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_product_card"))
        return
    
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("waiting_for_photo")  # Rasm yuborish qadami
    await state.update_data(photo_url=photo_url, nav_stack=nav_stack)
    await state.set_state(ProductCardStates.selecting_scene)
    await message.answer("Выберите вариант:", reply_markup=get_product_card_plans())


@router.message(ProductCardStates.waiting_for_photo)
async def product_card_invalid_input(message: Message, state: FSMContext):
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    await message.answer("❌ Для карточки нужно ровно одно фото.\n\nПожалуйста, отправьте фото.", reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_product_card"))


def get_back_button(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{current_step}"))
    return builder.as_markup()


@router.callback_query(F.data.startswith("back_"))
async def back_navigation_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("back_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if back_data == "to_root":
        await state.clear()
        await safe_edit_or_skip(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    
    if nav_stack:
        try:
            index = nav_stack.index(back_data)
            nav_stack = nav_stack[:index]  
            await state.update_data(nav_stack=nav_stack)
        except ValueError:
            nav_stack.pop()
            await state.update_data(nav_stack=nav_stack)
    
    if not nav_stack:
        await state.clear()
        await safe_edit_or_skip(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
        return

    prev_step = nav_stack[-1]
    if prev_step == "gen_product_card":
        await state.set_state(ProductCardStates.waiting_for_photo)
        await safe_edit_or_skip(callback,
            "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.\n\nЯ создам серию изображений по разным сценам.", 
            reply_markup=get_back_button("gen_product_card")
        )
    elif prev_step == "waiting_for_photo":
        await state.set_state(ProductCardStates.waiting_for_photo)
        await safe_edit_or_skip(callback,
            "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.",
            reply_markup=get_back_button("gen_product_card")
        )
    elif "selecting_scene_groups" in prev_step:
        await state.set_state(ProductCardStates.selecting_scene)
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=get_product_card_plans())
    elif "selecting_scene_group" in prev_step:
        groups = config_loader.get_scene_groups()
        await safe_edit_or_skip(callback, "Выберите группу сцен:", reply_markup=get_scene_groups(groups))
    elif "selecting_plan" in prev_step:
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        scenes = config_loader.get_scenes_by_group(group_id)
        await safe_edit_or_skip(callback,
            "Выберите сцену или создайте все:",
            reply_markup=get_scenes_in_group(scenes, group_id)
        )
    else:
        await state.clear()
        await safe_edit_or_skip(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())

@router.callback_query(ProductCardStates.selecting_scene, F.data == "pc_all_scenes")
async def product_card_all_scenes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("pc_all_scenes") 
    await state.update_data(nav_stack=nav_stack)
    
    scenes = config_loader.scenes.get("scenes", [])
    plans = ["far", "medium", "close"]
    total_results = len(scenes) * len(plans)
    cost = total_results * config_loader.pricing["product_card"]["per_result"]
    await state.update_data(generation_type="all_scenes", cost=cost, total_results=total_results)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button("selecting_scene")
            )
            return 
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Будет создано {total_results} изображений.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="pc_all_scenes")
    )


@router.callback_query(ProductCardStates.selecting_scene, F.data == "pc_select_scene")
async def product_card_select_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_scene_groups") 
    await state.update_data(nav_stack=nav_stack)
    groups = config_loader.get_scene_groups()
    await safe_edit_or_skip(callback, "Выберите группу сцен:", reply_markup=get_scene_groups(groups))


@router.callback_query(ProductCardStates.selecting_scene, F.data.startswith("scene_group_"))
async def select_scene_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = callback.data.replace("scene_group_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_scene_group") 
    await state.update_data(nav_stack=nav_stack, selected_group=group_id)
    scenes = config_loader.get_scenes_by_group(group_id)
    await safe_edit_or_skip(callback,
        "Выберите сцену или создайте все:",
        reply_markup=get_scenes_in_group(scenes, group_id)
    )


@router.callback_query(ProductCardStates.selecting_scene, F.data.startswith("scene_"))
async def select_specific_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if callback.data == "scene_back":
        nav_stack.pop()
        await state.update_data(nav_stack=nav_stack)
        groups = config_loader.get_scene_groups()
        await safe_edit_or_skip(callback, "Выберите группу сцен:", reply_markup=get_scene_groups(groups))
        return
    
    if callback.data.startswith("scene_all_"):
        group_id = callback.data.replace("scene_all_", "")
        scenes = config_loader.get_scenes_by_group(group_id)
        plans = ["far", "medium", "close"]
        total_results = len(scenes) * len(plans)
        cost = total_results * config_loader.pricing["product_card"]["per_result"]
        nav_stack.append("confirming_group")  # Confirm qadami
        await state.update_data(nav_stack=nav_stack, generation_type="group_scenes", selected_group=group_id, cost=cost, total_results=total_results)
        
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            has_balance = await user_repo.check_balance(callback.from_user.id, cost)
            if not has_balance:
                await safe_edit_or_skip(callback,
                    "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                    reply_markup=get_back_button("selecting_scene_group")
                )
                return
        
        await state.set_state(ProductCardStates.confirming)
        await safe_edit_or_skip(callback,
            f"Будет создано {total_results} изображений для группы.\nБудет списано {cost} кредитов.\n\nПродолжить?",
            reply_markup=get_confirmation_keyboard(cost, back_data="selecting_scene_group")
        )
        return
    
    scene_id = callback.data.replace("scene_", "")
    scene = config_loader.get_scene_by_id(scene_id)
    nav_stack.append("selecting_plan") 
    await state.update_data(nav_stack=nav_stack, selected_scene=scene_id)
    await state.set_state(ProductCardStates.selecting_plan)
    await safe_edit_or_skip(callback, "Выберите план съёмки:", reply_markup=get_scene_plans())


@router.callback_query(ProductCardStates.selecting_plan, F.data.startswith("plan_"))
async def select_plan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    plan = callback.data.split("_")[-1]
    cost = config_loader.pricing["product_card"]["per_result"]
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("confirming_single") 
    await state.update_data(nav_stack=nav_stack, generation_type="single_scene", selected_plan=plan, cost=cost, total_results=1)
    scene = config_loader.get_scene_by_id(data["selected_scene"])
    plan_names = {"far": "Дальний", "medium": "Средний", "close": "Крупный"}
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button("selecting_plan")
            )
            return
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Сцена: {scene['name']}\nПлан: {plan_names[plan]}\n\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="selecting_plan")
    )


@router.callback_query(ProductCardStates.confirming, F.data.startswith("confirm_"))
async def confirm_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    photo_url = data["photo_url"]
    cost = data["cost"]
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    
    await safe_edit_or_skip(callback, "⏳ Генерация началась...")
    
    try:
        data["photo_url"] = photo_url
        results = await kie_service.generate_product_cards(data)
        for i, result in enumerate(results, 1):
            if "image" in result:
                caption = f"Сцена: {result.get('scene_name', 'N/A')} · План: {result.get('plan', 'N/A')}"
                await callback.message.answer_photo(BufferedInputFile(result["image"], filename=f"result_{i}.jpg"), caption=caption)
        await callback.message.answer(f"✅ Генерация завершена!\n\nПотрачено: {cost} кредитов\nБаланс: {user.balance} кредитов", reply_markup=get_repeat_button())
    except Exception as e:
        logger.error(f"Product card generation error: {e}")
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.", reply_markup=get_back_to_generation())
    
    await state.clear()


def get_confirmation_keyboard(cost: int, back_data: str = "gen_product_card"):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"✅ Подтвердить ({cost} кредитов)", callback_data="confirm_product_card"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_{back_data}"))
    return builder.as_markup()