import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from states import VideoStates
from keyboards import (get_back_button_video, get_video_menu, get_video_scenarios, 
                       get_confirmation_keyboard, get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import UserRepository
from database.repositories import VideoScenarioRepository   # <-- YANGI
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
from utils.photo import get_photo_url_from_message
from config import settings

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


@router.callback_query(F.data == "gen_video")
async def video_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.update_data(nav_stack=["gen_video"])
    await callback.message.edit_text("🎬 Видео\n\nВыберите режим видео:", reply_markup=get_video_menu())


@router.callback_query(F.data.in_(["video_balance", "video_pro6", "video_pro10", "video_super6"]))
async def video_mode_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mode_map = {
        "video_balance": "balance",
        "video_pro6": "pro_6",
        "video_pro10": "pro_10",
        "video_super6": "super_6"
    }
    mode = mode_map[callback.data]
    video_config = config_loader.pricing["video"][mode]
    cost = video_config["cost"]
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append(f"video_mode_{mode}") 
    await state.update_data(nav_stack=nav_stack, mode=mode, cost=cost, model=video_config["model"], duration=video_config["duration"], resolution=video_config["resolution"])
    await state.set_state(VideoStates.waiting_for_photo)
    mode_names = {
        "balance": "⚖️ Баланс — Grok",
        "pro_6": "⭐ Про 6 сек — hailuo 768p",
        "pro_10": "⭐⭐ Про 10 сек — hailuo 768p",
        "super_6": "⭐⭐⭐ Супер Про 6 сек — hailuo 1080p"
    }
    await callback.message.edit_text(
        f"📸 Отправьте одно фото для генерации видео.\n\nРежим: {mode_names[mode]}\nСтоимость: {cost} кредитов\n\n✨ Можно отправить как фото или как файл", 
        reply_markup=get_back_button(f"video_mode_{mode}")
    )


def get_back_button(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"video_back_{current_step}"))
    return builder.as_markup()


@router.message(VideoStates.waiting_for_photo, F.photo | F.document)
async def video_photo_received(message: Message, state: FSMContext):
    try:
        photo_url = await get_photo_url_from_message(message)
    except ValueError as e:
        await message.answer(str(e), reply_markup=get_back_button("gen_video"))
        return
    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке фото. Попробуйте другое фото.", 
                           reply_markup=get_back_button("gen_video"))
        return
    
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("waiting_for_photo")
    await state.update_data(nav_stack=nav_stack, photo_url=photo_url)
    await state.set_state(VideoStates.selecting_scenario)

    async with async_session_maker() as session:
        vs_repo = VideoScenarioRepository(session)
        scenarios_db = await vs_repo.get_all()
        scenarios = [{"id": s.id, "name": s.name} for s in scenarios_db]

    await message.answer(
        "Выберите сценарий движения камеры или введите свой промпт:",
        reply_markup=get_video_scenarios(scenarios)
    )

@router.message(VideoStates.waiting_for_photo)
async def video_invalid_input(message: Message, state: FSMContext):
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    await message.answer("❌ Для видео нужно отправить фото.\n\nПожалуйста, отправьте фото (как фото или как файл).", reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_video"))


@router.callback_query(F.data.startswith("video_back_"))
async def back_navigation_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("video_back_", "")
    
    if back_data == "gen_video":
        await state.clear()
        await safe_edit_text(callback, 
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )
        return
    
    if back_data.startswith("video_mode_"):
        await state.clear()
        await safe_edit_text(callback,
            "🎬 Видео\n\nВыберите режим видео:",
            reply_markup=get_video_menu()
        )
        return
    
    if back_data == "waiting_for_photo":
        data = await state.get_data()
        mode = data.get("mode", "balance")
        video_config = config_loader.pricing["video"][mode]
        
        await state.set_state(VideoStates.waiting_for_photo)
        await state.update_data(mode=mode, cost=video_config["cost"], 
                              model=video_config["model"], 
                              duration=video_config["duration"],
                              resolution=video_config["resolution"])
        
        mode_names = {
            "balance": "⚖️ Баланс — Grok",
            "pro_6": "⭐ Про 6 сек — hailuo 768p",
            "pro_10": "⭐⭐ Про 10 сек — hailuo 768p",
            "super_6": "⭐⭐⭐ Супер Про 6 сек — hailuo 1080p"
        }
        
        await safe_edit_text(callback,
            f"📸 Отправьте одно фото для генерации видео.\n\nРежим: {mode_names.get(mode)}\nСтоимость: {video_config['cost']} кредитов\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button_video(f"video_mode_{mode}")
        )
        return
    
    if back_data in ["selecting_scenario", "back_selecting_scenario"]:
        data = await state.get_data()
        mode = data.get("mode", "balance")
        video_config = config_loader.pricing["video"][mode]

        await state.set_state(VideoStates.waiting_for_photo)

        mode_names = {
            "balance": "⚖️ Баланс — Grok",
            "pro_6": "⭐ Про 6 сек — hailuo 768p",
            "pro_10": "⭐⭐ Про 10 сек — hailuo 768p",
            "super_6": "⭐⭐⭐ Супер Про 6 сек — hailuo 1080p"
        }

        await safe_edit_text(callback,
            f"📸 Отправьте одно фото для генерации видео.\n\nРежим: {mode_names.get(mode)}\nСтоимость: {video_config['cost']} кредитов\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button_video("waiting_for_photo")
        )
        return

    if back_data in ["video_custom_prompt", "back_video_custom_prompt"]:
        await state.set_state(VideoStates.selecting_scenario)

        async with async_session_maker() as session:
            vs_repo = VideoScenarioRepository(session)
            scenarios_db = await vs_repo.get_all()
            scenarios = [{"id": s.id, "name": s.name} for s in scenarios_db]

        await safe_edit_text(callback,
            "Выберите сценарий движения камеры или введите свой промпт:",
            reply_markup=get_video_scenarios(scenarios)
        )
        return

@router.callback_query(VideoStates.selecting_scenario, F.data.startswith("video_scenario_"))
async def video_scenario_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_scenario") 
    await state.update_data(nav_stack=nav_stack)

    scenario_id = int(callback.data.replace("video_scenario_", ""))

    async with async_session_maker() as session:
        vs_repo = VideoScenarioRepository(session)
        scenario = await vs_repo.get_by_id(scenario_id)
        if not scenario or not scenario.is_active:
            await callback.message.edit_text("❌ Этот сценарий недоступен. Выберите другой.", reply_markup=get_back_button("waiting_for_photo"))
            return

        cost = data["cost"]
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await callback.message.edit_text("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_button("waiting_for_photo"))
            await state.clear()
            return

    await state.update_data(prompt=scenario.prompt, scenario_name=scenario.name)
    await callback.message.edit_text(
        f"Сценарий: {scenario.name}\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, "back_selecting_scenario")
    )
    await state.set_state(VideoStates.confirming)


@router.callback_query(VideoStates.selecting_scenario, F.data == "video_custom_prompt")
async def video_custom_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("video_custom_prompt") 
    await state.update_data(nav_stack=nav_stack)
    await callback.message.edit_text("✏️ Введите свой промпт для видео на русском или английском языке:", reply_markup=get_back_button("selecting_scenario"))
    await state.set_state(VideoStates.entering_custom_prompt)


@router.message(VideoStates.entering_custom_prompt, F.text)
async def video_custom_prompt_received(message: Message, state: FSMContext):
    custom_prompt = message.text
    translated_prompt = await translator_service.translate_ru_to_en(custom_prompt)
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("custom_prompt_received") 
    await state.update_data(nav_stack=nav_stack, prompt=translated_prompt, scenario_name="Свой промпт")
    cost = data["cost"]
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(message.from_user.id, cost)
        if not has_balance:
            await message.answer("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_button("video_custom_prompt"))
            await state.clear()
            return
    await message.answer(f"Ваш промпт: {translated_prompt}\n\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost, "back_video_custom_prompt"))
    await state.set_state(VideoStates.confirming)


@router.callback_query(VideoStates.confirming, F.data.startswith("confirm_"))
async def confirm_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    photo_url = data["photo_url"]
    prompt = data["prompt"]
    cost = data["cost"]
    model = data["model"]
    duration = int(data["duration"].split()[0].replace("~", ""))
    resolution = data["resolution"]

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    await callback.message.edit_text("⏳ Генерация видео... Это может занять несколько минут.")
    try:
        logger.info(f"Using image URL: {photo_url} for model {model}")
        result = await kie_service.generate_video(photo_url, prompt, model, duration, resolution)
        if "video" in result:
            await callback.message.answer_video(BufferedInputFile(result["video"], filename="video.mp4"), caption="✅ Видео готово!")
            await callback.message.answer(f"Потрачено: {cost} кредитов\nБаланс: {user.balance} кредитов", reply_markup=get_repeat_button())
        else:
            raise ValueError("No video in result")
    except Exception as e:
        logger.error(f"Video generation error: {e}", exc_info=True)
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(f"❌ Ошибка при генерации видео: {str(e)}\n\nКредиты возвращены на баланс.", reply_markup=get_back_to_generation())
    finally:
        await state.clear()
    await state.update_data(last_generation={
        "type": "video",
        "photo_url": photo_url,
        "prompt": prompt,
        "cost": cost,
        "model": model,
        "duration": str(duration),
        "resolution": resolution
    })