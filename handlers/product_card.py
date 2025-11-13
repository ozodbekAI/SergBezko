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


# ===== START =====
@router.callback_query(F.data == "gen_product_card")
async def product_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(ProductCardStates.waiting_for_photo)
    await send_bot_message(callback, "product_card", get_back_button("gen_product_card"))


# ===== PHOTO RECEIVED =====
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

    await state.update_data(photo_url=photo_url)

    # To‘g‘ridan-to‘g‘ri category ro‘yxatini ko‘rsatamiz
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


# ===== BACK NAVIGATION =====
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
        # Qayta category ro‘yxatini ko‘rsatamiz
        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)
            categories = await scene_repo.get_all_categories()

        builder = InlineKeyboardBuilder()
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
        await safe_edit_or_skip(
            callback,
            "Выберите категорию сцен:",
            reply_markup=builder.as_markup()
        )
        return


# ===== SELECT CATEGORY (bitta category -> ichidagi hammasi) =====
@router.callback_query(ProductCardStates.selecting_scene_category, F.data.startswith("pc_scene_cat_"))
async def select_scene_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
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
            "❌ В этой категории нет сцен (элементов).",
            reply_markup=get_back_button("selecting_scene_category")
        )
        return

    cost_per_result = config_loader.pricing["product_card"]["per_result"]
    cost = total_results * cost_per_result

    # Check balance
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

    # Statega saqlaymiz
    await state.update_data(
        photo_url=(await state.get_data())["photo_url"],
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


# ===== CONFIRM GENERATION (category ichidagi hammasi) =====
@router.callback_query(ProductCardStates.confirming, F.data == "pc_confirm_generation")
async def confirm_product_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    photo_url = data["photo_url"]
    cost = data["cost"]
    generation_type = data["generation_type"]
    selected_category = int(data["selected_category"])

    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)

    await safe_edit_or_skip(callback, "⏳ Генерация началась...")

    try:
        results = []

        async with async_session_maker() as session:
            scene_repo = SceneCategoryRepository(session)

            if generation_type == "category_all":
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

        # Natijalarni birma-bir yuboramiz
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

        await callback.message.answer(
            f"✅ Генерация завершена!\n\n"
            f"Потрачено: {cost} кредитов\n"
            f"Баланс: {user.balance} кредитов",
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

    # last_generation faqat info sifatida
    await state.clear()
    await state.update_data(last_generation={
        "type": "product_card",
        "photo_url": photo_url,
        "cost": cost,
        "generation_type": generation_type,
        "selected_category": selected_category,
        "total_results": data.get("total_results")
    })
