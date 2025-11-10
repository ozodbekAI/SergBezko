from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from states import NormalizeStates
from keyboards import (get_generation_menu, get_normalize_menu, get_model_types, 
                       get_confirmation_keyboard, get_repeat_button, get_back_to_generation)
from database import async_session_maker
from database.repositories import UserRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from config import settings
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "gen_normalize")
async def normalize_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.update_data(nav_stack=["gen_normalize"])
    await callback.message.edit_text("👗 Нормализация фото\n\nВыберите режим нормализации:", reply_markup=get_normalize_menu())

@router.callback_query(F.data == "norm_own_model")
async def normalize_own_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("norm_own_model")
    await state.update_data(nav_stack=nav_stack)
    await state.set_state(NormalizeStates.waiting_for_photos)
    await state.update_data(mode="own_model", photo_count=0, photo_urls=[])
    text = "📸 Отправьте два фото:\n\n1️⃣ Фото изделия/объекта\n2️⃣ Фото вашей модели (лицо/фигура)\n\nОтправляйте по одному фото."
    await callback.message.edit_text(text, reply_markup=get_back_button(nav_stack[-1]))

@router.callback_query(F.data == "norm_new_model")
async def normalize_new_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("norm_new_model")
    await state.update_data(nav_stack=nav_stack)
    await state.set_state(NormalizeStates.waiting_for_photos)
    await state.update_data(mode="new_model", photo_urls=[])
    await callback.message.edit_text("📸 Отправьте одно фото изделия/объекта.", reply_markup=get_back_button(nav_stack[-1]))

@router.message(NormalizeStates.waiting_for_photos, F.photo)
async def normalize_photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        nav_stack = data.get("nav_stack", [])
        await message.answer("❌ Пожалуйста, отправляйте фото по ОДНОМУ (не альбомом).", 
                           reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_normalize"))
        return
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    mode = data["mode"]
    photo_urls = data.get("photo_urls", [])
    photo_count = data.get("photo_count", 0)
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
    photo_urls.append(photo_url)
    photo_count += 1
    if mode == "own_model":
        if photo_count < 2:
            nav_stack.append("waiting_photo_1")
            await state.update_data(nav_stack=nav_stack, photo_urls=photo_urls, photo_count=photo_count)
            await message.answer(f"✅ Фото {photo_count}/2 получено.\n\nОтправьте второе фото.", reply_markup=get_back_button("waiting_photo_1"))
        else:
            cost = config_loader.pricing["normalize"]["own_model"]
            nav_stack.append("confirming_own")
            await state.update_data(nav_stack=nav_stack, photo_urls=photo_urls, photo_count=photo_count, cost=cost)
            async with async_session_maker() as session:
                user_repo = UserRepository(session)
                has_balance = await user_repo.check_balance(message.from_user.id, cost)
                if not has_balance:
                    await message.answer("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_button(nav_stack[-2] if len(nav_stack) > 1 else "norm_own_model"))
                    await state.clear()
                    return
            await message.answer(f"Будет списано {cost} кредита.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost, "confirming_own"))
            await state.set_state(NormalizeStates.confirming)
    elif mode == "new_model":
        nav_stack.append("selecting_model_type")
        await state.update_data(nav_stack=nav_stack, photo_urls=photo_urls)
        models = config_loader.model_types.get("model_types", [])
        await message.answer("Выберите тип фотомодели:", reply_markup=get_model_types(models))
        await state.set_state(NormalizeStates.selecting_model_type)


@router.message(NormalizeStates.waiting_for_photos)
async def normalize_invalid_input(message: Message, state: FSMContext):
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    mode = data["mode"]
    if mode == "own_model":
        text = "❌ Для этого режима нужно ровно два фото — изделие и модель."
    else:
        text = "❌ Для этого режима нужно одно фото."
    await message.answer(text + "\n\nПожалуйста, отправьте фото.", reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_normalize"))


@router.callback_query(NormalizeStates.selecting_model_type, F.data.startswith("model_"))
async def select_model_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    model_id = callback.data.split("_")[-1]
    cost = config_loader.pricing["normalize"]["new_model"]
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("confirming_new")
    await state.update_data(nav_stack=nav_stack, model_type=model_id, cost=cost)
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await callback.message.edit_text("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_button("selecting_model_type"))
            await state.clear()
            return
    try:
        model = config_loader.get_model_type_by_id(model_id)
    except ValueError as e:
        logger.error(f"Model type lookup error: {e}")
        await callback.message.edit_text("❌ Тип модели не найден. Вернуться к выбору?", reply_markup=get_model_types(config_loader.model_types.get("model_types", [])))
        await state.set_state(NormalizeStates.selecting_model_type)
        return
    await callback.message.edit_text(f"Выбрана модель: {model['name']}\n\nБудет списано {cost} кредита.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost, "confirming_new"))
    await state.set_state(NormalizeStates.confirming)


@router.callback_query(NormalizeStates.confirming, F.data.startswith("confirm_"))
async def confirm_normalize(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    mode = data["mode"]
    photo_urls = data["photo_urls"]
    cost = data["cost"]
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    await callback.message.edit_text("⏳ Нормализация началась...")
    try:
        if mode == "own_model":
            result = await kie_service.normalize_own_model(photo_urls[0], photo_urls[1])
        else:
            model_type = data["model_type"]
            try:
                model = config_loader.get_model_type_by_id(model_type)
            except ValueError as e:
                logger.error(f"Model type lookup error in confirm: {e}")
                raise ValueError("Тип модели не найден")
            result = await kie_service.normalize_new_model(photo_urls[0], model["prompt"])
        if "image" in result:
            await callback.message.answer_photo(BufferedInputFile(result["image"], filename="normalized.jpg"), caption="✅ Нормализация завершена!")
            await callback.message.answer(f"Потрачено: {cost} кредита\nБаланс: {user.balance} кредитов", reply_markup=get_repeat_button())
        else:
            raise ValueError("No image in result")
    except Exception as e:
        logger.error(f"Normalize error: {e}")
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(f"❌ Ошибка при нормализации: {str(e)}\n\nКредиты возвращены на баланс.", reply_markup=get_back_to_generation())
    await state.clear()


@router.callback_query(F.data.startswith("back_"))
async def back_navigation_normalize(callback: CallbackQuery, state: FSMContext):
    """Back handler normalize uchun – FIXED: To'liq navigatsiya logikasi"""
    await callback.answer()
    back_data = callback.data.replace("back_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if back_data == "back_to_generation":
        await state.clear()
        await callback.message.edit_text("Выберите тип генерации:", reply_markup=get_generation_menu())
        return

    if nav_stack and nav_stack[-1] == back_data:
        nav_stack.pop()
        await state.update_data(nav_stack=nav_stack)

    if not nav_stack:
        await state.clear()
        await callback.message.edit_text("Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    
    prev_step = nav_stack[-1] if nav_stack else None
    mode = data.get("mode")
    
    if prev_step == "gen_normalize":
        await callback.message.edit_text("👗 Нормализация фото\n\nВыберите режим нормализации:", reply_markup=get_normalize_menu())
        return
    
    if prev_step in ["norm_own_model", "norm_new_model", "waiting_photo_1", "selecting_model_type", "confirming_own", "confirming_new"]:
        await state.update_data(mode=None, photo_urls=[], photo_count=0, model_type=None)
        await callback.message.edit_text("👗 Нормализация фото\n\nВыберите режим нормализации:", reply_markup=get_normalize_menu())
        return

    await state.clear()
    await callback.message.edit_text("Выберите тип генерации:", reply_markup=get_generation_menu())


@router.callback_query(F.data == "cancel")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Операция отменена")
    await callback.message.edit_text("❌ Операция отменена.", reply_markup=get_back_to_generation())
    await state.clear()

def get_back_button(current_step: str):
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{current_step}"))
    return builder.as_markup()


def get_confirmation_keyboard(cost: int, back_data: str = "confirming") -> InlineKeyboardMarkup:  
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{cost}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_{back_data}")
    )
    return builder.as_markup()