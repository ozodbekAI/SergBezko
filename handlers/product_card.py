from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from handlers.start import send_bot_message
from states import ProductCardStates
from keyboards import (get_back_button_product_card, get_confirmation_keyboard_product_card, 
                       get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import UserRepository, SceneCategoryRepository
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

def get_back_button_with_buy(current_step: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💳 Пополнить баланс", 
        callback_data="cabinet_balance"
    ))
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
    await send_bot_message(callback, "product_card", get_back_button("gen_product_card"))


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
    await state.set_state(ProductCardStates.selecting_scene_category)
    
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
        await state.set_state(ProductCardStates.selecting_scene_category)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return
    
    if back_data == "selecting_scene_category":
        await state.set_state(ProductCardStates.selecting_scene_category)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return
    
    if back_data == "selecting_scene_subcategory":
        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)
            categories = await scene_repo.get_all_categories()
        
        await state.set_state(ProductCardStates.selecting_scene_category)
        
        builder = InlineKeyboardBuilder()
        for category in categories:
            builder.row(InlineKeyboardButton(
                text=category.name,
                callback_data=f"pc_scene_cat_{category.id}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_category"))
        
        await safe_edit_or_skip(callback,
            "Выберите категорию сцен:",
            reply_markup=builder.as_markup()
        )
        return
    
    if back_data == "selecting_scene_item":
        data = await state.get_data()
        category_id = int(data.get("selected_category", 0))
        
        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)
            category = await scene_repo.get_category(category_id)
            subcategories = await scene_repo.get_subcategories_by_category(category_id)
        
        await state.set_state(ProductCardStates.selecting_scene_subcategory)
        
        builder = InlineKeyboardBuilder()
        
        builder.row(InlineKeyboardButton(
            text="✅ Все подкатегории",
            callback_data=f"pc_all_subcats_{category_id}"
        ))
        
        for subcat in subcategories:
            items = await scene_repo.get_items_by_subcategory(subcat.id)
            items_count = len(items)
            
            builder.row(InlineKeyboardButton(
                text=f"{subcat.name} ({items_count} вариантов)",
                callback_data=f"pc_subcat_{subcat.id}_{category_id}"
            ))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_subcategory"))
        
        await safe_edit_or_skip(callback,
            f"🌆 <b>{category.name}</b>\n\nВыберите подкатегорию:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    
    if back_data in ["confirming_single", "confirming_group", "confirming_all"]:
        await state.set_state(ProductCardStates.selecting_scene_category)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📋 Все сцены", callback_data="pc_all_scenes"))
        builder.row(InlineKeyboardButton(text="🎯 Выбрать сцену", callback_data="pc_select_scene"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_waiting_for_photo"))
        await safe_edit_or_skip(callback, "Выберите вариант:", reply_markup=builder.as_markup())
        return


@router.callback_query(ProductCardStates.selecting_scene_category, F.data == "pc_all_scenes")
async def product_card_all_scenes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        hierarchy = await scene_repo.get_full_hierarchy()
    
    # Hisoblash: barcha category -> subcategory -> items
    total_results = sum(
        len(sc["items"])
        for cat in hierarchy.values()
        for sc in cat["subcategories"].values()
    )
    
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
                reply_markup=get_back_button_with_buy("waiting_for_photo")
            )
            return 
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Будет создано {total_results} изображений.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_all")
    )


@router.callback_query(ProductCardStates.selecting_scene_category, F.data == "pc_select_scene")
async def product_card_select_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        categories = await scene_repo.get_all_categories()
    
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.row(InlineKeyboardButton(
            text=category.name,
            callback_data=f"pc_scene_cat_{category.id}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_category"))
    
    await safe_edit_or_skip(callback, "Выберите категорию сцен:", reply_markup=builder.as_markup())


@router.callback_query(ProductCardStates.selecting_scene_category, F.data.startswith("pc_scene_cat_"))
async def select_scene_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category_id = int(callback.data.replace("pc_scene_cat_", ""))
    
    await state.update_data(selected_category=category_id)
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        category = await scene_repo.get_category(category_id)
        subcategories = await scene_repo.get_subcategories_by_category(category_id)
    
    await state.set_state(ProductCardStates.selecting_scene_subcategory)
    
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="✅ Все подкатегории",
        callback_data=f"pc_all_subcats_{category_id}"
    ))

    for subcat in subcategories:
        items = await scene_repo.get_items_by_subcategory(subcat.id)
        items_count = len(items)
        
        builder.row(InlineKeyboardButton(
            text=f"{subcat.name} ({items_count} вариантов)",
            callback_data=f"pc_subcat_{subcat.id}_{category_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_subcategory"))
    
    await safe_edit_or_skip(callback,
        f"🌆 <b>{category.name}</b>\n\nВыберите подкатегорию:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_scene_subcategory, F.data.startswith("pc_all_subcats_"))
async def select_all_subcats_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category_id = int(callback.data.replace("pc_all_subcats_", ""))
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        subcategories = await scene_repo.get_subcategories_by_category(category_id)
    
    # Hisoblash: barcha subcategory ichidagi itemlar
    total_results = 0
    for subcat in subcategories:
        items = await scene_repo.get_items_by_subcategory(subcat.id)
        total_results += len(items)
    
    cost = total_results * config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="category_all_subcats",
        selected_category=category_id,
        cost=cost,
        total_results=total_results
    )
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_scene_item")
            )
            return
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Будет создано {total_results} изображений для всех подкатегорий.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_group")
    )


@router.callback_query(ProductCardStates.selecting_scene_subcategory, F.data.startswith("pc_subcat_"))
async def select_subcategory(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_", 3)
    subcategory_id = int(parts[2])
    category_id = int(parts[3])
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        subcategory = await scene_repo.get_subcategory(subcategory_id)
        items = await scene_repo.get_items_by_subcategory(subcategory_id)
    
    if not items:
        await safe_edit_or_skip(callback,
            "❌ В этой подкатегории нет элементов!",
            reply_markup=get_back_button("selecting_scene_item")
        )
        return
    
    await state.update_data(selected_subcategory=subcategory_id)
    await state.set_state(ProductCardStates.selecting_scene_item)
    
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="✅ Все элементы",
        callback_data=f"pc_all_items_{subcategory_id}"
    ))
    
    for item in items:
        builder.row(InlineKeyboardButton(
            text=item.name,
            callback_data=f"pc_item_{item.id}_{subcategory_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pc_back_selecting_scene_item"))
    
    await safe_edit_or_skip(callback,
        f"📸 <b>{subcategory.name}</b>\n\nВыберите элемент:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_scene_item, F.data.startswith("pc_all_items_"))
async def select_all_items(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    subcategory_id = int(callback.data.replace("pc_all_items_", ""))
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        items = await scene_repo.get_items_by_subcategory(subcategory_id)
    
    total_results = len(items)
    cost = total_results * config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="subcategory_all_items",
        selected_subcategory=subcategory_id,
        cost=cost,
        total_results=total_results
    )
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_scene_item")
            )
            return
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Будет создано {total_results} изображений.\nБудет списано {cost} кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="confirming_group")
    )


@router.callback_query(ProductCardStates.selecting_scene_item, F.data.startswith("pc_item_"))
async def select_item(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_", 3)
    item_id = int(parts[2])
    subcategory_id = int(parts[3])
    
    cost = config_loader.pricing["product_card"]["per_result"]
    
    await state.update_data(
        generation_type="single_item",
        selected_item=item_id,
        selected_subcategory=subcategory_id,
        cost=cost,
        total_results=1
    )
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_scene_item")
            )
            return
        
        scene_repo = SceneCategoryRepository(session)
        item = await scene_repo.get_item(item_id)
        subcategory = await scene_repo.get_subcategory(subcategory_id)
    
    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(callback,
        f"Подкатегория: {subcategory.name}\nЭлемент: {item.name}\n\nБудет списано {cost} кредитов.\n\nПродолжить?",
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
            scene_repo = SceneCategoryRepository(session)
            
            if generation_type == "all_scenes":
                # Barcha category -> subcategory -> items
                hierarchy = await scene_repo.get_full_hierarchy()
                
                for cat_id, cat_data in hierarchy.items():
                    for subcat_id, subcat_data in cat_data["subcategories"].items():
                        for item in subcat_data["items"]:
                            result = await kie_service.change_scene(photo_url, item["prompt"])
                            result["category_name"] = cat_data["name"]
                            result["subcategory_name"] = subcat_data["name"]
                            result["item_name"] = item["name"]
                            results.append(result)
            
            elif generation_type == "category_all_subcats":
                # Bitta category, barcha subcategory -> items
                category_id = int(data["selected_category"])
                category = await scene_repo.get_category(category_id)
                subcategories = await scene_repo.get_subcategories_by_category(category_id)
                
                for subcat in subcategories:
                    items = await scene_repo.get_items_by_subcategory(subcat.id)
                    for item in items:
                        result = await kie_service.change_scene(photo_url, item.prompt)
                        result["category_name"] = category.name
                        result["subcategory_name"] = subcat.name
                        result["item_name"] = item.name
                        results.append(result)
            
            elif generation_type == "subcategory_all_items":
                # Bitta subcategory, barcha items
                subcategory_id = int(data["selected_subcategory"])
                subcategory = await scene_repo.get_subcategory(subcategory_id)
                category = await scene_repo.get_category(subcategory.category_id)
                items = await scene_repo.get_items_by_subcategory(subcategory_id)
                
                for item in items:
                    result = await kie_service.change_scene(photo_url, item.prompt)
                    result["category_name"] = category.name
                    result["subcategory_name"] = subcategory.name
                    result["item_name"] = item.name
                    results.append(result)
            
            elif generation_type == "single_item":
                # Bitta item
                item_id = int(data["selected_item"])
                item = await scene_repo.get_item(item_id)
                subcategory = await scene_repo.get_subcategory(item.subcategory_id)
                category = await scene_repo.get_category(subcategory.category_id)
                
                result = await kie_service.change_scene(photo_url, item.prompt)
                result["category_name"] = category.name
                result["subcategory_name"] = subcategory.name
                result["item_name"] = item.name
                results.append(result)
        
        for i, result in enumerate(results, 1):
            if "image" in result:
                caption = f"{result.get('category_name', 'N/A')} · {result.get('subcategory_name', 'N/A')} · {result.get('item_name', 'N/A')}"
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
        "selected_category": data.get("selected_category"),
        "selected_subcategory": data.get("selected_subcategory"),
        "selected_item": data.get("selected_item"),
        "total_results": data.get("total_results")
    })