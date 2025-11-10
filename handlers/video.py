# video.py (to'liq fix – nav_stack qo'shildi, back tiklash)
import logging  # FIXED
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from states import VideoStates
from keyboards import (get_video_menu, get_video_scenarios, 
                       get_confirmation_keyboard, get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import UserRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
from config import settings

logger = logging.getLogger(__name__)  # FIXED
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
    await state.update_data(nav_stack=["gen_video"])  # FIXED: Stack boshlash
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
    mode_names = {
        "balance": "⚖️ Баланс — Grok",
        "pro_6": "⭐ Про 6 сек — hailuo 768p",
        "pro_10": "⭐⭐ Про 10 сек — hailuo 768p",
        "super_6": "⭐⭐⭐ Супер Про 6 сек — hailuo 1080p"
    }
    await callback.message.edit_text(f"📸 Отправьте одно фото для генерации видео.\n\nРежим: {mode_names[mode]}\nСтоимость: {cost} кредитов", reply_markup=get_back_button("video_mode_" + mode))  # FIXED


def get_back_button(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{current_step}"))
    return builder.as_markup()


@router.message(VideoStates.waiting_for_photo, F.photo)
async def video_photo_received(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("waiting_for_photo")  # FIXED
    await state.update_data(nav_stack=nav_stack, photo=file_id)
    await state.set_state(VideoStates.selecting_scenario)
    scenarios = config_loader.video_scenarios.get("video_scenarios", [])
    await message.answer("Выберите сценарий движения камеры или введите свой промпт:", reply_markup=get_video_scenarios(scenarios))


@router.message(VideoStates.waiting_for_photo)
async def video_invalid_input(message: Message, state: FSMContext):
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    await message.answer("❌ Для видео можно отправить только одно фото.\n\nПожалуйста, отправьте фото.", reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_video"))


@router.callback_query(F.data.startswith("back_"))
async def back_navigation_video(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("back_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if nav_stack and nav_stack[-1] == back_data:
        nav_stack.pop()
        await state.update_data(nav_stack=nav_stack)
    
    if not nav_stack:
        await state.clear()
        await callback.message.edit_text("Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    
    prev_step = nav_stack[-1]
    if prev_step == "gen_video":
        await state.clear()
        await callback.message.edit_text("🎬 Видео\n\nВыберите режим видео:", reply_markup=get_video_menu())
        return
    
    if "video_mode_" in prev_step:
        await state.set_state(VideoStates.waiting_for_photo)
        await callback.message.edit_text("📸 Отправьте одно фото для генерации видео.", reply_markup=get_back_button(prev_step))
        return
    
    if prev_step == "waiting_for_photo":
        await state.clear()
        await callback.message.edit_text("🎬 Видео\n\nВыберите режим видео:", reply_markup=get_video_menu())
        return
    
    # Default
    await safe_edit_text(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
    await state.clear()


@router.callback_query(VideoStates.selecting_scenario, F.data.startswith("video_scenario_"))
async def video_scenario_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_scenario") 
    await state.update_data(nav_stack=nav_stack)
    scenario_id = callback.data.replace("video_scenario_", "")
    scenario = config_loader.get_video_scenario_by_id(scenario_id)
    cost = data["cost"]
    await state.update_data(prompt=scenario["prompt"], scenario_name=scenario["name"])
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await callback.message.edit_text("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_button("waiting_for_photo"))
            await state.clear()
            return
    await callback.message.edit_text(f"Сценарий: {scenario['name']}\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost, "back_selecting_scenario"))
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
    file_id = data["photo"] 
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
        file = await callback.bot.get_file(file_id)
        photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
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