from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from handlers.start import send_bot_message
from states import ProductCardStates
from keyboards import (
    get_back_button_product_card, get_confirmation_keyboard_product_card,
    get_repeat_button, get_back_to_generation, get_generation_menu
)
from database import async_session_maker
from database.repositories import UserRepository, SceneCategoryRepository
from services.config_loader import config_loader
from services.kie_service import kie_service
from utils.photo import get_photo_url_from_message
from config import settings
import logging
import zipfile
import io
from datetime import datetime

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


def get_confirmation_keyboard(cost: int, back_data: str = "selecting_scene_category"):
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


def get_back_and_download_buttons(download: bool = True):
    """Generatsiya tugagandan keyin ZIP yuklash tugmalari"""
    builder = InlineKeyboardBuilder()
    if download:
        builder.row(InlineKeyboardButton(
            text="📥 Скачать все",
            callback_data="pc_download_all"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="pc_back_selecting_scene_category"
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
        await message.answer(
            "❌ Для карточки нужно ровно ОДНО фото (не альбом).",
            reply_markup=get_back_button("gen_product_card")
        )
        return

    try:
        photo_url = await get_photo_url_from_message(message)
    except ValueError as e:
        await message.answer(str(e), reply_markup=get_back_button("gen_product_card"))
        return
    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при обработке фото. Попробуйте другое фото.",
            reply_markup=get_back_button("gen_product_card")
        )
        return

    await state.update_data(photo_url=photo_url, selected_categories=[])

    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        categories = await scene_repo.get_all_categories()

    if not categories:
        await message.answer(
            "❌ Нет доступных категорий сцен.",
            reply_markup=get_back_button("gen_product_card")
        )
        return

    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="✅ Все сцены",
        callback_data="pc_scene_cat_all"
    ))
    
    builder.row(InlineKeyboardButton(
        text="🎯 Выбрать несколько",
        callback_data="pc_select_multiple"
    ))

    for category in categories:
        builder.row(InlineKeyboardButton(
            text=category.name,
            callback_data=f"pc_scene_cat_{category.id}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="pc_back_waiting_for_photo"
    ))

    await state.set_state(ProductCardStates.selecting_scene_category)
    await message.answer("Выберите категорию сцен:", reply_markup=builder.as_markup())


@router.message(ProductCardStates.waiting_for_photo)
async def product_card_invalid_input(message: Message, state: FSMContext):
    await message.answer(
        "❌ Для карточки нужно отправить фото.\n\n"
        "Пожалуйста, отправьте фото (как фото или как файл).",
        reply_markup=get_back_button("gen_product_card")
    )


@router.callback_query(F.data.startswith("pc_back_"))
async def back_navigation_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("pc_back_", "")

    if back_data in ["gen_product_card", "to_root"]:
        await state.clear()
        await safe_edit_or_skip(
            callback,
            "Выберите тип генерации:",
            reply_markup=get_generation_menu()
        )
        return

    if back_data == "waiting_for_photo":
        await state.set_state(ProductCardStates.waiting_for_photo)
        await safe_edit_or_skip(
            callback,
            "📦 Готовая карточка товара\n\n"
            "📸 Отправьте ОДНО фото для создания карточки товара.\n\n"
            "Я создам серию изображений по разным сценам.\n\n"
            "✨ Можно отправить как фото или как файл",
            reply_markup=get_back_button("gen_product_card")
        )
        return

    if back_data == "selecting_scene_category":
        data = await state.get_data()
        photo_url = data.get("photo_url")
        
        if not photo_url:
            await state.set_state(ProductCardStates.waiting_for_photo)
            await safe_edit_or_skip(
                callback,
                "📦 Готовая карточка товара\n\n"
                "📸 Отправьте ОДНО фото для создания карточки товара.\n\n"
                "Я создам серию изображений по разным сценам.\n\n"
                "✨ Можно отправить как фото или как файл",
                reply_markup=get_back_button("gen_product_card")
            )
            return

        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)
            categories = await scene_repo.get_all_categories()

        builder = InlineKeyboardBuilder()
        
        builder.row(InlineKeyboardButton(
            text="✅ Все сцены",
            callback_data="pc_scene_cat_all"
        ))
        
        builder.row(InlineKeyboardButton(
            text="🎯 Выбрать несколько",
            callback_data="pc_select_multiple"
        ))
        
        for category in categories:
            builder.row(InlineKeyboardButton(
                text=category.name,
                callback_data=f"pc_scene_cat_{category.id}"
            ))
        
        builder.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="pc_back_waiting_for_photo"
        ))

        await state.update_data(selected_categories=[])
        await state.set_state(ProductCardStates.selecting_scene_category)
        await safe_edit_or_skip(
            callback,
            "Выберите категорию сцен:",
            reply_markup=builder.as_markup()
        )
        return

    if back_data == "selecting_multiple_categories":
        data = await state.get_data()
        
        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)
            categories = await scene_repo.get_all_categories()

        builder = InlineKeyboardBuilder()
        
        builder.row(InlineKeyboardButton(
            text="✅ Все сцены",
            callback_data="pc_scene_cat_all"
        ))
        
        builder.row(InlineKeyboardButton(
            text="🎯 Выбрать несколько",
            callback_data="pc_select_multiple"
        ))
        
        for category in categories:
            builder.row(InlineKeyboardButton(
                text=category.name,
                callback_data=f"pc_scene_cat_{category.id}"
            ))
        
        builder.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="pc_back_waiting_for_photo"
        ))

        await state.update_data(selected_categories=[])
        await state.set_state(ProductCardStates.selecting_scene_category)
        await safe_edit_or_skip(
            callback,
            "Выберите категорию сцен:",
            reply_markup=builder.as_markup()
        )
        return


@router.callback_query(ProductCardStates.selecting_scene_category, F.data == "pc_scene_cat_all")
async def select_all_scenes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        hierarchy = await scene_repo.get_full_hierarchy()
        
        total_results = 0
        for cat_id, cat in hierarchy.items():
            for sub_id, sub in cat["subcategories"].items():
                total_results += len(sub["items"])

    if total_results == 0:
        await safe_edit_or_skip(
            callback,
            "❌ Нет доступных сцен.",
            reply_markup=get_back_button("selecting_scene_category")
        )
        return

    cost_per_result = config_loader.pricing["product_card"]["per_result"]
    cost = total_results * cost_per_result

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(
                callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_scene_category")
            )
            return

    await state.update_data(
        generation_type="all_scenes",
        cost=cost,
        total_results=total_results
    )

    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(
        callback,
        f"Будет создано изображений: <b>{total_results}</b> (все сцены)\n"
        f"Будет списано: <b>{cost}</b> кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="selecting_scene_category"),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_scene_category, F.data == "pc_select_multiple")
async def select_multiple_categories(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        categories = await scene_repo.get_all_categories()

    if not categories:
        await safe_edit_or_skip(
            callback,
            "❌ Нет доступных категорий.",
            reply_markup=get_back_button("selecting_scene_category")
        )
        return

    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])
    
    builder = InlineKeyboardBuilder()

    for category in categories:
        is_selected = category.id in selected_categories
        emoji = "✅ " if is_selected else ""
        builder.row(InlineKeyboardButton(
            text=f"{emoji}{category.name}",
            callback_data=f"pc_toggle_cat_{category.id}"
        ))
    
    builder.row(InlineKeyboardButton(
        text=f"✅ Готово ({len(selected_categories)} выбрано)",
        callback_data="pc_done_selecting_categories"
    ))
    
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="pc_back_selecting_scene_category"
    ))

    await state.set_state(ProductCardStates.selecting_multiple_categories)
    
    await safe_edit_or_skip(
        callback,
        f"Выберите категории для генерации:\n\n"
        f"Выбрано: <b>{len(selected_categories)}</b>\n\n"
        f"Нажмите на категорию чтобы выбрать/отменить",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_multiple_categories, F.data.startswith("pc_toggle_cat_"))
async def toggle_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.replace("pc_toggle_cat_", ""))
    
    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])

    if category_id in selected_categories:
        selected_categories.remove(category_id)
        await callback.answer("❌ Убрано")
    else:
        selected_categories.append(category_id)
        await callback.answer("✅ Добавлено")

    await state.update_data(selected_categories=selected_categories)

    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        categories = await scene_repo.get_all_categories()

    builder = InlineKeyboardBuilder()
    
    for category in categories:
        is_selected = category.id in selected_categories
        emoji = "✅ " if is_selected else ""
        builder.row(InlineKeyboardButton(
            text=f"{emoji}{category.name}",
            callback_data=f"pc_toggle_cat_{category.id}"
        ))
    
    builder.row(InlineKeyboardButton(
        text=f"✅ Готово ({len(selected_categories)} выбрано)",
        callback_data="pc_done_selecting_categories"
    ))
    
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="pc_back_selecting_multiple_categories"
    ))

    await safe_edit_or_skip(
        callback,
        f"Выберите категории для генерации:\n\n"
        f"Выбрано: <b>{len(selected_categories)}</b>\n\n"
        f"Нажмите на категорию чтобы выбрать/отменить",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_multiple_categories, F.data == "pc_done_selecting_categories")
async def done_selecting_categories(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    selected_categories = data.get("selected_categories", [])

    if not selected_categories:
        await callback.answer("❌ Вы не выбрали ни одной категории!", show_alert=True)
        return

    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        total_results = 0
        
        for category_id in selected_categories:
            subcategories = await scene_repo.get_subcategories_by_category(category_id)
            for subcat in subcategories:
                items = await scene_repo.get_items_by_subcategory(subcat.id)
                total_results += len(items)

    if total_results == 0:
        await safe_edit_or_skip(
            callback,
            "❌ В выбранных категориях нет сцен.",
            reply_markup=get_back_button("selecting_multiple_categories")
        )
        return

    cost_per_result = config_loader.pricing["product_card"]["per_result"]
    cost = total_results * cost_per_result

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(
                callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_multiple_categories")
            )
            return

    await state.update_data(
        generation_type="selected_categories",
        cost=cost,
        total_results=total_results
    )

    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(
        callback,
        f"Будет создано изображений: <b>{total_results}</b>\n"
        f"Будет списано: <b>{cost}</b> кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="selecting_multiple_categories"),
        parse_mode="HTML"
    )


@router.callback_query(ProductCardStates.selecting_scene_category, F.data.startswith("pc_scene_cat_"))
async def select_scene_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    if callback.data == "pc_scene_cat_all":
        return
    
    category_id = int(callback.data.replace("pc_scene_cat_", ""))

    async with async_session_maker() as session:
        scene_repo = SceneCategoryRepository(session)
        category = await scene_repo.get_category(category_id)
        subcategories = await scene_repo.get_subcategories_by_category(category_id)

        all_items = []
        for subcat in subcategories:
            items = await scene_repo.get_items_by_subcategory(subcat.id)
            all_items.extend([
                {
                    "id": item.id,
                    "name": item.name,
                    "prompt": item.prompt,
                    "subcategory_name": subcat.name
                }
                for item in items
            ])

    total_results = len(all_items)
    if total_results == 0:
        await safe_edit_or_skip(
            callback,
            "❌ В этой категории нет сцен.",
            reply_markup=get_back_button("selecting_scene_category")
        )
        return

    cost_per_result = config_loader.pricing["product_card"]["per_result"]
    cost = total_results * cost_per_result

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(callback.from_user.id, cost)
        if not has_balance:
            await safe_edit_or_skip(
                callback,
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_button_with_buy("selecting_scene_category")
            )
            return

    await state.update_data(
        generation_type="category_all",
        selected_category=category_id,
        cost=cost,
        total_results=total_results
    )

    await state.set_state(ProductCardStates.confirming)
    await safe_edit_or_skip(
        callback,
        f"Категория: <b>{category.name}</b>\n\n"
        f"Будет создано изображений: <b>{total_results}</b>\n"
        f"Будет списано: <b>{cost}</b> кредитов.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost, back_data="selecting_scene_category"),
        parse_mode="HTML"
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
                hierarchy = await scene_repo.get_full_hierarchy()
                for cat_id, cat in hierarchy.items():
                    cat_name = cat["name"]
                    for sub_id, sub in cat["subcategories"].items():
                        sub_name = sub["name"]
                        for item in sub["items"]:
                            result = await kie_service.change_scene(photo_url, item["prompt"])
                            result["category_name"] = cat_name
                            result["subcategory_name"] = sub_name
                            result["item_name"] = item["name"]
                            results.append(result)

            elif generation_type == "category_all":
                selected_category = int(data["selected_category"])
                category = await scene_repo.get_category(selected_category)
                subcategories = await scene_repo.get_subcategories_by_category(selected_category)

                for subcat in subcategories:
                    items = await scene_repo.get_items_by_subcategory(subcat.id)
                    for item in items:
                        result = await kie_service.change_scene(photo_url, item.prompt)
                        result["category_name"] = category.name
                        result["subcategory_name"] = subcat.name
                        result["item_name"] = item.name
                        results.append(result)

            elif generation_type == "selected_categories":
                selected_categories = data.get("selected_categories", [])
                
                for category_id in selected_categories:
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

        for i, result in enumerate(results, 1):
            if "image" in result:
                caption = (
                    f"{result.get('category_name', 'N/A')} · "
                    f"{result.get('subcategory_name', 'N/A')} · "
                    f"{result.get('item_name', 'N/A')}"
                )
                await callback.message.answer_photo(
                    BufferedInputFile(result["image"], filename=f"result_{i}.jpg"),
                    caption=caption
                )

        await state.update_data(generated_results=results)

        await callback.message.answer(
            f"✅ Генерация завершена!\n\n"
            f"Потрачено: {cost} кредитов\n"
            f"Баланс: {user.balance} кредитов",
            reply_markup=get_back_and_download_buttons()
        )
    except Exception as e:
        logger.error(f"Product card generation error: {e}", exc_info=True)
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.",
            reply_markup=get_back_button("selecting_scene_category")
        )


@router.callback_query(F.data == "pc_download_all")
async def download_all_as_zip(callback: CallbackQuery, state: FSMContext):
    await callback.answer("📦 Создаю ZIP архив...")
    
    data = await state.get_data()
    results = data.get("generated_results", [])
    
    if not results:
        await callback.message.answer(
            "❌ Нет изображений для скачивания",
            reply_markup=get_back_and_download_buttons()
        )
        return
    
    status_msg = await callback.message.answer("⏳ Подготовка архива...")
    
    try:
        MAX_ZIP_SIZE = 45 * 1024 * 1024 
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        zip_parts = []
        current_zip = io.BytesIO()
        current_size = 0
        part_number = 1
        images_in_current_part = 0
        
        current_zipfile = zipfile.ZipFile(current_zip, 'w', zipfile.ZIP_DEFLATED)
        
        for i, result in enumerate(results, 1):
            if "image" in result:
                cat = result.get('category_name', 'N/A')[:20]
                sub = result.get('subcategory_name', 'N/A')[:20]
                item = result.get('item_name', 'N/A')[:20]
                
                filename = f"{i:03d}_{cat}_{sub}_{item}.jpg"
                filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.')).strip()
                filename = filename[:100] if len(filename) > 100 else filename
                
                image_data = result["image"]
                image_size = len(image_data)
                
                if current_size + image_size > MAX_ZIP_SIZE and images_in_current_part > 0:
                    current_zipfile.close()
                    current_zip.seek(0)
                    zip_parts.append((current_zip.getvalue(), part_number, images_in_current_part))
                    
                    await status_msg.edit_text(
                        f"⏳ Создан архив {part_number}... Продолжаю..."
                    )

                    current_zip = io.BytesIO()
                    current_size = 0
                    part_number += 1
                    images_in_current_part = 0
                    current_zipfile = zipfile.ZipFile(current_zip, 'w', zipfile.ZIP_DEFLATED)

                current_zipfile.writestr(filename, image_data)
                current_size += image_size
                images_in_current_part += 1
        
        current_zipfile.close()
        current_zip.seek(0)
        zip_parts.append((current_zip.getvalue(), part_number, images_in_current_part))
        
        try:
            await status_msg.delete()
        except:
            pass
        
        if len(zip_parts) == 1:
            try:
                await callback.message.answer_document(
                    BufferedInputFile(
                        zip_parts[0][0],
                        filename=f"product_cards_{timestamp}.zip"
                    ),
                    caption=f"📦 Все изображения ({len(results)} шт.)",
                    reply_markup=get_back_and_download_buttons(download=False),
                    request_timeout=300  
                )
            except Exception as e:
                logger.error(f"Failed to send single ZIP: {e}")
                await callback.message.answer(
                    "❌ Файл слишком большой для отправки.\n"
                    "Попробуйте выбрать меньше категорий.",
                    reply_markup=get_back_and_download_buttons(download=False)
                )
        else:
            sent_parts = 0
            for zip_data, part_num, img_count in zip_parts:
                try:
                    await callback.message.answer_document(
                        BufferedInputFile(
                            zip_data,
                            filename=f"product_cards_{timestamp}_part{part_num}.zip"
                        ),
                        caption=f"📦 Часть {part_num}/{len(zip_parts)} ({img_count} изображений)",
                        request_timeout=300  
                    )
                    sent_parts += 1
                except Exception as e:
                    logger.error(f"Failed to send ZIP part {part_num}: {e}")
                    await callback.message.answer(
                        f"❌ Ошибка при отправке части {part_num}",
                        reply_markup=get_back_and_download_buttons(download=False)
                    )
                    break
            
            if sent_parts == len(zip_parts):
                await callback.message.answer(
                    f"✅ Все файлы отправлены!\n\n"
                    f"Всего частей: {len(zip_parts)}\n"
                    f"Изображений: {len(results)}",
                    reply_markup=get_back_and_download_buttons(download=False)
                )
        
    except Exception as e:
        logger.error(f"ZIP creation error: {e}", exc_info=True)
        try:
            await status_msg.delete()
        except:
            pass
        
        await callback.message.answer(
            "❌ Ошибка при создании архива.\n"
            "Попробуйте выбрать меньше изображений.",
            reply_markup=get_back_and_download_buttons()
        )