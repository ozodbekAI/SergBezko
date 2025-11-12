from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from states import ProductCardStates
from keyboards import (get_back_button_product_card, get_confirmation_keyboard_product_card, 
                       get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import UserRepository, SceneRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from utils.photo import get_photo_url_from_message
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


def get_back_button(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"pc_back_{current_step}"))
    return builder.as_markup()


def get_confirmation_keyboard(cost: int, back_data: str = "gen_product_card"):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"✅ Подтвердить ({cost} кредитов)", 
        callback_data="pc_confirm_generation"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отмена", 
        callback_data=f"pc_back_{back_data}"
    ))
    return builder.as_markup()


@router.callback_query(F.data == "gen_product_card")
async def product_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(ProductCardStates.waiting_for_photo)
    await callback.message.edit_text(
        "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.\n\nЯ создам серию изображений по разным сценам.\n\n✨ Можно отправить как фото или как файл", 
        reply_markup=get_back_button("gen_product_card")
    )


@router.message(ProductCardStates.waiting_for_photo, F.photo | F.document)
async def product_card_photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        await message.answer("❌ Для карточки нужно ровно ОДНО фото (не альбом).", 
                           reply_markup=get_back_button("gen_product_card"))
        return
    
    try:
        photo_url = await get_photo_url_from_message(message)
    except ValueError as e:
        await message.answer(str(e), reply_markup=get_back_button("gen_product_card"))
        return
    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке фото. Попробуйте другое фото.", 
                           reply_markup=get_back_button("gen_product_card"))
        return
    
    await state.update_data(photo_url=photo_url)
    await state.set_state(ProductCardStates.selecting_scene)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
    builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
    
    await message.answer("Выберите вариант:", reply_markup=builder.as_markup())


@router.message(ProductCardStates.waiting_for_photo)
async def product_card_invalid_input(message: Message, state: FSMContext):
    await message.answer("❌ Для карточки нужно отправить фото.\n\nПожалуйста, отправьте фото (как фото или как файл).", 
                        reply_markup=get_back_button("gen_product_card"))


@router.callback_query(F.data.startswith("pc_back_"))
async def back_navigation_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("pc_back_", "")
    
    if back_data in ["gen_product_card", "to_root"]:
        await state.clear()
        await safe_edit_or_skip(callback,
            "Выберите тип генерации:",
            reply_markup=get_generation_menu()
        )
        return
    
    if back_data == "waiting_for_photo":
        await state.set_state(ProductCardStates.waiting_for_photo)
        await safe_edit_or_skip(callback,
            "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.\n\nЯ создам серию изображений по разным сценам.\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button("gen_product_card")
        )
        return
    
    if back_data == "pc_all_scenes":
        await state.set_state(ProductCardStates.selecting_scene)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return
    
    if back_data == "selecting_scene_groups":
        await state.set_state(ProductCardStates.selecting_scene)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return
    
    if back_data == "selecting_scene_group":
        async with async_session_maker() as session:
            scene_repo = SceneRepository(session)
            groups = await scene_repo.get_all_groups()
        
        await state.set_state(ProductCardStates.selecting_scene)
        
        builder = InlineKeyboardBuilder()
        for group in groups:
            builder.row(InlineKeyboardButton(
                text=group.name,
                callback_data=f"pc_scene_group_{group.id}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_groups"))
        
        await safe_edit_or_skip(callback,
            "Выберите группу сцен:",
            reply_markup=builder.as_markup()
        )
        return
    
    if back_data == "selecting_plan":
        data = await state.get_data()
        group_id = int(data.get("selected_group", 0))
        
        async with async_session_maker() as session:
            scene_repo = SceneRepository(session)
            group = await scene_repo.get_group(group_id)
            plans = await scene_repo.get_all_plans()
        
        await state.set_state(ProductCardStates.selecting_plan)
        
        builder = InlineKeyboardBuilder()
        
        builder.row(InlineKeyboardButton(
            text="✅ Все планы группы",
            callback_data=f"pc_all_plans_{group_id}"
        ))
        
        for plan in plans:
            prompts = await scene_repo.get_prompts_by_group_and_plan(group_id, plan.id)
            prompts_count = len(prompts)
            
            builder.row(InlineKeyboardButton(
                text=f"{plan.name} ({prompts_count} вариантов)",
                callback_data=f"pc_plan_{plan.id}_{group_id}"
            ))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_group"))
        
        await safe_edit_or_skip(callback,
            f"🌆 <b>{group.name}</b>\n\nВыберите план съёмки:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    
    if back_data in ["confirming_single", "confirming_group", "confirming_all"]:
        await state.set_state(ProductCardStates.selecting_scene)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return


@router.callback_query(ProductCardStates.selecting_scene, F.data == "pc_all_scenes")
async def product_card_all_scenes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneRepository(session)
        groups = await scene_repo.get_all_groups()
        plans = await scene_repo.get_all_plans()
    
    total_results = len(groups) * len(plans)
    cost = total_results * config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="all_scenes", 
        cost=cost, 
        total_results=total_results
    )
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button("waiting_for_photo")
            )
            return 
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Будет создано {total_results} изображений.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_all")
    )


@router.callback_query(ProductCardStates.selecting_scene, F.data == "pc_select_scene")
async def product_card_select_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneRepository(session)
        groups = await scene_repo.get_all_groups()
    
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.row(InlineKeyboardButton(
            text=group.name,
            callback_data=f"pc_scene_group_{group.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_groups"))
    
    await safe_edit_or_skip(callback, "Выберите группу сцен:", reply_markup=builder.as_markup())


@router.callback_query(ProductCardStates.selecting_scene, F.data.startswith("pc_scene_group_"))
async def select_scene_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pc_scene_group_", ""))
    
    await state.update_data(selected_group=group_id)
    
    async with async_session_maker() as session:
        scene_repo = SceneRepository(session)
        group = await scene_repo.get_group(group_id)
        plans = await scene_repo.get_all_plans()
    
    await state.set_state(ProductCardStates.selecting_plan)
    
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="✅ Все планы группы",
        callback_data=f"pc_all_plans_{group_id}"
    ))

    for plan in plans:
        prompts = await scene_repo.get_prompts_by_group_and_plan(group_id, plan.id)
        prompts_count = len(prompts)
        
        builder.row(InlineKeyboardButton(
            text=f"{plan.name} ({prompts_count} вариантов)",
            callback_data=f"pc_plan_{plan.id}_{group_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_group"))
    
    await safe_edit_or_skip(callback,
        f"🌆 <b>{group.name}</b>\n\nВыберите план съёмки:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_plan, F.data.startswith("pc_all_plans_"))
async def select_all_plans_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pc_all_plans_", ""))
    
    async with async_session_maker() as session:
        scene_repo = SceneRepository(session)
        plans = await scene_repo.get_all_plans()
    
    total_results = len(plans)
    cost = total_results * config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="group_all_plans",
        selected_group=group_id,
        cost=cost,
        total_results=total_results
    )
    
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
        f"Будет создано {total_results} изображений для всех планов группы.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_group")
    )


@router.callback_query(ProductCardStates.selecting_plan, F.data.startswith("pc_plan_"))
async def select_plan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_", 3)
    plan_id = int(parts[2])
    group_id = int(parts[3])
    
    cost = config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="single_plan",
        selected_plan=plan_id,
        selected_group=group_id,
        cost=cost,
        total_results=1
    )
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button("selecting_plan")
            )
            return
        
        scene_repo = SceneRepository(session)
        group = await scene_repo.get_group(group_id)
        plan = await scene_repo.get_plan(plan_id)
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Сцена: {group.name}\nПлан: {plan.name}\n\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_single")
    )


@router.callback_query(ProductCardStates.confirming, F.data == "pc_confirm_generation")
async def confirm_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    photo_url = data["photo_url"]
    cost = data["cost"]
    generation_type = data["generation_type"]

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    
    await safe_edit_or_skip(callback, "⏳ Генерация началась...")
    
    try:
        results = []
        
        async with async_session_maker() as session:
            scene_repo = SceneRepository(session)
            
            if generation_type == "all_scenes":
                # Все группы и все планы
                groups = await scene_repo.get_all_groups()
                plans = await scene_repo.get_all_plans()
                
                for group in groups:
                    for plan in plans:
                        prompts = await scene_repo.get_prompts_by_group_and_plan(group.id, plan.id)
                        if prompts:
                            # Берем первый промпт из группы
                            prompt = prompts[0]
                            print("PLAN PROMPT:", prompt.prompt)
                            result = await kie_service.change_scene(photo_url, prompt.prompt)
                            result["scene_name"] = group.name
                            result["plan"] = plan.name
                            results.append(result)
            
            elif generation_type == "group_all_plans":
                # Одна группа, все планы
                group_id = int(data["selected_group"])
                group = await scene_repo.get_group(group_id)
                plans = await scene_repo.get_all_plans()
                
                for plan in plans:
                    prompts = await scene_repo.get_prompts_by_group_and_plan(group_id, plan.id)
                    if prompts:
                        prompt = prompts[0]
                        result = await kie_service.change_scene(photo_url, prompt.prompt)
                        result["scene_name"] = group.name
                        result["plan"] = plan.name
                        results.append(result)
            
            elif generation_type == "single_plan":
                group_id = int(data["selected_group"])
                plan_id = int(data["selected_plan"])
                group = await scene_repo.get_group(group_id)
                plan = await scene_repo.get_plan(plan_id)
                prompts = await scene_repo.get_prompts_by_group_and_plan(group_id, plan_id)
                
                if prompts:
                    prompt = prompts[0]
                    result = await kie_service.change_scene(photo_url, prompt.prompt)
                    result["scene_name"] = group.name
                    result["plan"] = plan.name
                    results.append(result)
        
        for i, result in enumerate(results, 1):
            if "image" in result:
                caption = f"Сцена: {result.get('scene_name', 'N/A')} · План: {result.get('plan', 'N/A')}"
                await callback.message.answer_photo(
                    BufferedInputFile(result["image"], filename=f"result_{i}.jpg"),
                    caption=caption
                )
        
        await callback.message.answer(
            f"✅ Генерация завершена!\n\nПотрачено: {cost} кредитов\nБаланс: {user.balance} кредитов",
            reply_markup=get_repeat_button()
        )
    except Exception as e:
        logger.error(f"Product card generation error: {e}", exc_info=True)
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.",
            reply_markup=get_back_to_generation()
        )
    
    await state.clear()
    await state.update_data(last_generation={
        "type": "product_card",
        "photo_url": photo_url,
        "cost": cost,
        "generation_type": generation_type,
        "selected_group": data.get("selected_group"),
        "selected_plan": data.get("selected_plan"),
        "total_results": data.get("total_results")
    })