from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from states import NormalizeStates
from keyboards import (get_back_button_normalize, get_back_button_normalize_with_buy, get_generation_menu, get_normalize_menu,
                       get_confirmation_keyboard_normalize, get_repeat_button, get_back_to_generation)
from database import async_session_maker
from database.repositories import UserRepository, ModelCategoryRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from utils.photo import get_photo_url_from_message
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "gen_normalize")
async def normalize_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("👗 Нормализация фото\n\nВыберите режим нормализации:", reply_markup=get_normalize_menu())


@router.callback_query(F.data == "norm_own_model")
async def normalize_own_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(NormalizeStates.waiting_for_photos)
    await state.update_data(mode="own_model", photo_count=0, photo_urls=[])
    text = "📸 Отправьте два фото:\n\n1️⃣ Фото изделия/объекта\n2️⃣ Фото вашей модели (лицо/фигура)\n\nОтправляйте по одному фото.\n\n✨ Можно отправить как фото или как файл"
    await callback.message.edit_text(text, reply_markup=get_back_button_normalize("norm_own_model"))


@router.callback_query(F.data == "norm_new_model")
async def normalize_new_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(NormalizeStates.waiting_for_photos)
    await state.update_data(mode="new_model", photo_urls=[])
    await callback.message.edit_text("📸 Отправьте одно фото изделия/объекта.\n\n✨ Можно отправить как фото или как файл", reply_markup=get_back_button_normalize("norm_new_model"))


@router.message(NormalizeStates.waiting_for_photos, F.photo | F.document)
async def normalize_photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        mode = data.get("mode")
        back_step = "norm_own_model" if mode == "own_model" else "norm_new_model"
        await message.answer("❌ Пожалуйста, отправляйте фото по ОДНОМУ (не альбомом).", 
                           reply_markup=get_back_button_normalize(back_step))
        return
    
    try:
        photo_url = await get_photo_url_from_message(message)
    except ValueError as e:
        await message.answer(str(e), reply_markup=get_back_button_normalize("gen_normalize"))
        return
    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке фото. Попробуйте другое фото.", 
                           reply_markup=get_back_button_normalize("gen_normalize"))
        return
    
    data = await state.get_data()
    mode = data["mode"]
    photo_urls = data.get("photo_urls", [])
    photo_count = data.get("photo_count", 0)
    
    photo_urls.append(photo_url)
    photo_count += 1
    
    if mode == "own_model":
        if photo_count < 2:
            await state.update_data(photo_urls=photo_urls, photo_count=photo_count)
            await message.answer(f"✅ Фото {photo_count}/2 получено.\n\nОтправьте второе фото.", 
                               reply_markup=get_back_button_normalize("waiting_photo_1"))
        else:
            cost = config_loader.pricing["normalize"]["own_model"]
            await state.update_data(photo_urls=photo_urls, photo_count=photo_count, cost=cost)
            
            async with async_session_maker() as session:
                user_repo = UserRepository(session)
                has_balance = await user_repo.check_balance(message.from_user.id, cost)
                if not has_balance:
                    await message.answer("❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", 
                                       reply_markup=get_back_button_normalize_with_buy("norm_own_model"))
                    await state.clear()
                    return
            
            await message.answer(f"Будет списано {cost} кредита.\n\nПродолжить?", 
                               reply_markup=get_confirmation_keyboard_normalize(cost, "confirming_own"))
            await state.set_state(NormalizeStates.confirming)
            
    elif mode == "new_model":
        await state.update_data(photo_urls=photo_urls)
        
        # YANGI: 3-darajali struktura
        async with async_session_maker() as session:
            repo = ModelCategoryRepository(session)
            categories = await repo.get_all_categories()
        
        if not categories:
            await message.answer("❌ Категории моделей не найдены!", reply_markup=get_back_button_normalize("norm_new_model"))
            return
        
        kb = InlineKeyboardBuilder()
        for category in categories:
            kb.row(InlineKeyboardButton(text=category.name, callback_data=f"norm_model_cat_{category.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="norm_back_norm_new_model"))
        
        await message.answer("Выберите категорию модели:", reply_markup=kb.as_markup())
        await state.set_state(NormalizeStates.selecting_model_category)


@router.message(NormalizeStates.waiting_for_photos)
async def normalize_invalid_input(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode")
    back_step = "norm_own_model" if mode == "own_model" else "norm_new_model"
    
    if mode == "own_model":
        text = "❌ Для этого режима нужно ровно два фото — изделие и модель."
    else:
        text = "❌ Для этого режима нужно одно фото."
    
    await message.answer(text + "\n\nПожалуйста, отправьте фото (как фото или как файл).", reply_markup=get_back_button_normalize(back_step))


# ===== SELECT CATEGORY =====
@router.callback_query(NormalizeStates.selecting_model_category, F.data.startswith("norm_model_cat_"))
async def select_model_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.replace("norm_model_cat_", ""))
    await callback.answer()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        category = await repo.get_category(category_id)
        subcategories = await repo.get_subcategories_by_category(category_id)
    
    if not subcategories:
        await callback.message.edit_text("❌ В этой категории нет подкатегорий!", reply_markup=get_back_button_normalize("selecting_model_category"))
        return
    
    kb = InlineKeyboardBuilder()
    for subcat in subcategories:
        kb.row(InlineKeyboardButton(text=subcat.name, callback_data=f"norm_model_subcat_{category_id}_{subcat.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="norm_back_selecting_model_category"))
    
    await callback.message.edit_text(
        f"<b>{category.name}</b>\n\nВыберите подкатегорию:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(NormalizeStates.selecting_model_subcategory)
    await state.update_data(model_category_id=category_id)


# ===== SELECT SUBCATEGORY =====
@router.callback_query(NormalizeStates.selecting_model_subcategory, F.data.startswith("norm_model_subcat_"))
async def select_model_subcategory(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.replace("norm_model_subcat_", "").split("_")
    category_id = int(parts[0])
    subcategory_id = int(parts[1])
    await callback.answer()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        subcategory = await repo.get_subcategory(subcategory_id)
        items = await repo.get_items_by_subcategory(subcategory_id)
    
    if not items:
        await callback.message.edit_text("❌ В этой подкатегории нет элементов!", reply_markup=get_back_button_normalize("selecting_model_category"))
        return
    
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.row(InlineKeyboardButton(text=item.name, callback_data=f"norm_model_item_{item.id}"))
    kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"norm_model_cat_{category_id}"))
    
    await callback.message.edit_text(
        f"<b>{subcategory.name}</b>\n\nВыберите тип модели:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(NormalizeStates.selecting_model_item)
    await state.update_data(model_subcategory_id=subcategory_id)


# ===== SELECT ITEM & CONFIRM =====
@router.callback_query(NormalizeStates.selecting_model_item, F.data.startswith("norm_model_item_"))
async def select_model_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("norm_model_item_", ""))
    await callback.answer()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        item = await repo.get_item(item_id)
    
    cost = config_loader.pricing["normalize"]["new_model"]
    await state.update_data(model_item_id=item_id, model_prompt=item.prompt, cost=cost)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await callback.message.edit_text(
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", 
                reply_markup=get_back_button_normalize_with_buy("selecting_model_item")
            )
            await state.clear()
            return
    
    await callback.message.edit_text(
        f"Выбрана модель: <b>{item.name}</b>\n\nБудет списано {cost} кредита.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard_normalize(cost, "confirming_new"),
        parse_mode="HTML"
    )
    await state.set_state(NormalizeStates.confirming)


# ===== CONFIRM & GENERATE =====
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
            model_prompt = data["model_prompt"]
            result = await kie_service.normalize_new_model(photo_urls[0], model_prompt)
        
        if "image" in result:
            await callback.message.answer_photo(
                BufferedInputFile(result["image"], filename="normalized.jpg"), 
                caption="✅ Нормализация завершена!"
            )
            await callback.message.answer(
                f"Потрачено: {cost} кредита\nБаланс: {user.balance} кредитов", 
                reply_markup=get_repeat_button()
            )
        else:
            raise ValueError("No image in result")
    except Exception as e:
        logger.error(f"Normalize error: {e}")
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(
            f"❌ Ошибка при нормализации: {str(e)}\n\nКредиты возвращены на баланс.", 
            reply_markup=get_back_to_generation()
        )
    
    await state.clear()
    await state.update_data(last_generation={
        "type": "normalize",
        "mode": mode,
        "photo_urls": photo_urls,
        "cost": cost,
        "model_prompt": data.get("model_prompt")
    })


# ===== BACK NAVIGATION =====
@router.callback_query(F.data.startswith("norm_back_"))
async def back_navigation_normalize(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("norm_back_", "")
    
    if back_data == "gen_normalize":
        await state.clear()
        await callback.message.edit_text("Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    
    if back_data in ["norm_own_model", "norm_new_model"]:
        await state.clear()
        await callback.message.edit_text("👗 Нормализация фото\n\nВыберите режим нормализации:", reply_markup=get_normalize_menu())
        return
    
    if back_data == "waiting_photo_1":
        await state.set_state(NormalizeStates.waiting_for_photos)
        await state.update_data(mode="own_model", photo_count=0, photo_urls=[])
        await callback.message.edit_text(
            "📸 Отправьте два фото:\n\n1️⃣ Фото изделия/объекта\n2️⃣ Фото вашей модели (лицо/фигура)\n\nОтправляйте по одному фото.\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button_normalize("norm_own_model")
        )
        return
    
    if back_data == "selecting_model_category":
        data = await state.get_data()
        photo_urls = data.get("photo_urls", [])
        await state.set_state(NormalizeStates.waiting_for_photos)
        await state.update_data(mode="new_model", photo_urls=photo_urls)
        await callback.message.edit_text(
            "📸 Отправьте одно фото изделия/объекта.\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button_normalize("norm_new_model")
        )
        return
    
    if back_data == "confirming_own":
        await state.set_state(NormalizeStates.waiting_for_photos)
        await state.update_data(mode="own_model", photo_count=0, photo_urls=[])
        await callback.message.edit_text(
            "📸 Отправьте два фото:\n\n1️⃣ Фото изделия/объекта\n2️⃣ Фото вашей модели (лицо/фигура)\n\nОтправляйте по одному фото.\n\n✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button_normalize("norm_own_model")
        )
        return
    
    if back_data == "confirming_new":
        await state.set_state(NormalizeStates.selecting_model_item)
        data = await state.get_data()
        subcategory_id = data.get("model_subcategory_id")
        
        async with async_session_maker() as session:
            repo = ModelCategoryRepository(session)
            items = await repo.get_items_by_subcategory(subcategory_id)
        
        kb = InlineKeyboardBuilder()
        for item in items:
            kb.row(InlineKeyboardButton(text=item.name, callback_data=f"norm_model_item_{item.id}"))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"norm_model_cat_{data.get('model_category_id')}"))
        
        await callback.message.edit_text("Выберите тип модели:", reply_markup=kb.as_markup())
        return


@router.callback_query(F.data == "cancel")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Операция отменена")
    await callback.message.edit_text("❌ Операция отменена.", reply_markup=get_back_to_generation())
    await state.clear()