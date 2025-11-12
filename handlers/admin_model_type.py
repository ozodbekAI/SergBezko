from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import ModelCategoryRepository, AdminLogRepository
from states import AdminModelCategoryStates
from admin_keyboards import (
    get_model_category_main_menu,
    get_model_categories_list,
    get_model_subcategories_list,
    get_model_items_list,
    get_admin_back_keyboard,
    get_cancel_keyboard,
    get_confirm_delete_keyboard
)
import logging

logger = logging.getLogger(__name__)
router = Router(name="admin_model_categories")


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if callback.message.text != text or callback.message.reply_markup != reply_markup:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Edit failed: {e}")

@router.callback_query(F.data == "admin_model_types")
async def admin_model_categories_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        hierarchy = await repo.get_full_hierarchy()
    
    total_cats = len(hierarchy)
    total_subcats = sum(len(c["subcategories"]) for c in hierarchy.values())
    total_items = sum(
        len(sc["items"]) 
        for c in hierarchy.values() 
        for sc in c["subcategories"].values()
    )
    
    text = (
        f"👗 <b>Управление моделями</b>\n\n"
        f"📊 Статистика:\n"
        f"• Категорий: {total_cats}\n"
        f"• Подкатегорий: {total_subcats}\n"
        f"• Элементов: {total_items}\n\n"
    )
    
    if hierarchy:
        text += "<b>Структура:</b>\n\n"
        for cid, c in hierarchy.items():
            text += f"<b>{c['name']}</b>\n"
            for scid, sc in c["subcategories"].items():
                text += f"   ├── {sc['name']}\n"
                for item in sc["items"][:2]:
                    text += f"      └── {item['name']}\n"
                if len(sc["items"]) > 2:
                    text += f"      └── ...еще {len(sc['items']) - 2}\n"
            text += "\n"
    
    await safe_edit_text(callback, text, reply_markup=get_model_category_main_menu())


@router.callback_query(F.data == "model_cat_add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminModelCategoryStates.entering_category_name)
    
    await safe_edit_text(
        callback,
        "➕ <b>Добавление категории</b>\n\n"
        "Введите название категории:\n"
        "<i>Например: 👗 Одежда</i>",
        reply_markup=get_cancel_keyboard("model_cat_cancel")
    )


@router.message(AdminModelCategoryStates.entering_category_name, F.text)
async def add_category_name(message: Message, state: FSMContext):
    name = message.text.strip()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        category = await repo.add_category(name)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_model_category",
            f"Added: {category.name} (ID: {category.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Категория добавлена!\n\n"
        f"Название: {name}\n"
        f"ID: {category.id}",
        reply_markup=get_admin_back_keyboard("model_cat_cancel")
    )


@router.callback_query(F.data == "model_cat_add_subcategory")
async def add_subcategory_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        categories = await repo.get_all_categories()
    
    if not categories:
        await safe_edit_text(
            callback,
            "❌ Сначала добавьте категорию!",
            reply_markup=get_admin_back_keyboard("model_cat_cancel")
        )
        return
    
    await state.set_state(AdminModelCategoryStates.selecting_category)
    await safe_edit_text(
        callback,
        "➕ <b>Добавление подкатегории</b>\n\n"
        "Выберите категорию:",
        reply_markup=get_model_categories_list(categories, "add_subcat")
    )


@router.callback_query(AdminModelCategoryStates.selecting_category, F.data.startswith("model_cat_add_subcat_"))
async def select_category_for_subcategory(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category_id = int(callback.data.replace("model_cat_add_subcat_", ""))
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        category = await repo.get_category(category_id)
    
    await state.update_data(category_id=category_id, category_name=category.name)
    await state.set_state(AdminModelCategoryStates.entering_subcategory_name)
    
    await safe_edit_text(
        callback,
        f"Категория: <b>{category.name}</b>\n\n"
        f"Введите название подкатегории:\n"
        f"<i>Например: Платья / Куртки</i>",
        reply_markup=get_cancel_keyboard("model_cat_cancel")
    )


@router.message(AdminModelCategoryStates.entering_subcategory_name, F.text)
async def add_subcategory_name(message: Message, state: FSMContext):
    data = await state.get_data()
    category_id = data["category_id"]
    name = message.text.strip()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        subcategory = await repo.add_subcategory(category_id, name)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_model_subcategory",
            f"Added: {subcategory.name} to {data['category_name']} (ID: {subcategory.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Подкатегория добавлена!\n\n"
        f"Категория: {data['category_name']}\n"
        f"Название: {name}\n"
        f"ID: {subcategory.id}",
        reply_markup=get_admin_back_keyboard("model_cat_cancel")
    )


@router.callback_query(F.data == "model_cat_add_item")
async def add_item_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        categories = await repo.get_all_categories()
    
    if not categories:
        await safe_edit_text(
            callback,
            "❌ Сначала добавьте категорию и подкатегорию!",
            reply_markup=get_admin_back_keyboard("model_cat_cancel")
        )
        return
    
    await state.set_state(AdminModelCategoryStates.selecting_category)
    await safe_edit_text(
        callback,
        "➕ <b>Добавление элемента</b>\n\n"
        "Выберите категорию:",
        reply_markup=get_model_categories_list(categories, "add_item")
    )


@router.callback_query(AdminModelCategoryStates.selecting_category, F.data.startswith("model_cat_add_item_"))
async def select_category_for_item(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category_id = int(callback.data.replace("model_cat_add_item_", ""))
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        category = await repo.get_category(category_id)
        subcategories = await repo.get_subcategories_by_category(category_id)
    
    if not subcategories:
        await safe_edit_text(
            callback,
            f"❌ В категории <b>{category.name}</b> нет подкатегорий!",
            get_admin_back_keyboard("model_cat_cancel")
        )
        return
    
    await state.update_data(category_id=category_id, category_name=category.name)
    await state.set_state(AdminModelCategoryStates.selecting_subcategory)
    
    await safe_edit_text(
        callback,
        f"Категория: <b>{category.name}</b>\n\n"
        f"Выберите подкатегорию:",
        reply_markup=get_model_subcategories_list(subcategories, category_id, "add_item")
    )


@router.callback_query(AdminModelCategoryStates.selecting_subcategory, F.data.startswith("model_subcat_add_item_"))
async def select_subcategory_for_item(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("model_subcat_add_item_", "").split("_")
    subcategory_id = int(parts[1])
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        subcategory = await repo.get_subcategory(subcategory_id)
    
    data = await state.get_data()
    await state.update_data(
        subcategory_id=subcategory_id,
        subcategory_name=subcategory.name
    )
    await state.set_state(AdminModelCategoryStates.entering_item_name)
    
    await safe_edit_text(
        callback,
        f"Категория: <b>{data['category_name']}</b>\n"
        f"Подкатегория: <b>{subcategory.name}</b>\n\n"
        f"Введите название (рус.):\n"
        f"<i>Например: Красное платье</i>",
        reply_markup=get_cancel_keyboard("model_cat_cancel")
    )


@router.message(AdminModelCategoryStates.entering_item_name, F.text)
async def add_item_name(message: Message, state: FSMContext):
    name = message.text.strip()
    data = await state.get_data()
    
    await state.update_data(item_name=name)
    await state.set_state(AdminModelCategoryStates.entering_item_prompt)
    
    await message.answer(
        f"Категория: <b>{data['category_name']}</b>\n"
        f"Подкатегория: <b>{data['subcategory_name']}</b>\n"
        f"Название: <b>{name}</b>\n\n"
        f"Теперь введите промпт (англ.):\n"
        f"<i>Например: red dress, elegant style</i>",
        reply_markup=get_cancel_keyboard("model_cat_cancel")
    )


@router.message(AdminModelCategoryStates.entering_item_prompt, F.text)
async def add_item_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    subcategory_id = data["subcategory_id"]
    name = data["item_name"]
    prompt = message.text.strip()
    
    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        item = await repo.add_item(subcategory_id, name, prompt)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_model_item",
            f"Added: {item.name} (ID: {item.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Элемент добавлен!\n\n"
        f"Категория: {data['category_name']}\n"
        f"Подкатегория: {data['subcategory_name']}\n"
        f"Название: {name}\n"
        f"Промпт: <code>{prompt}</code>\n"
        f"ID: {item.id}",
        reply_markup=get_admin_back_keyboard("model_cat_cancel")
    )


@router.callback_query(F.data == "model_cat_edit_menu")
async def model_edit_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        categories = await repo.get_all_categories()

    if not categories:
        await safe_edit_text(
            callback,
            "Редактировать нечего — категорий нет!",
            reply_markup=get_admin_back_keyboard("admin_model_types")
        )
        return

    await safe_edit_text(
        callback,
        "<b>Редактирование</b>\n\nВыберите категорию:",
        reply_markup=get_model_categories_list(categories, "edit")
    )


@router.callback_query(F.data.startswith("model_cat_edit_"))
async def model_edit_select_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cat_id = int(callback.data.replace("model_cat_edit_", ""))

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        cat = await repo.get_category(cat_id)
        subcats = await repo.get_subcategories_by_category(cat_id)

    if not subcats:
        await safe_edit_text(
            callback,
            f"В категории <b>{cat.name}</b> нет подкатегорий!",
            reply_markup=get_admin_back_keyboard("model_cat_edit_menu")
        )
        return

    await state.update_data(selected_cat_id=cat_id)
    await safe_edit_text(
        callback,
        f"<b>{cat.name}</b>\n\nВыберите подкатегорию:",
        reply_markup=get_model_subcategories_list(subcats, cat_id, "edit")
    )


@router.callback_query(F.data.startswith("model_subcat_edit_"))
async def model_edit_select_subcategory(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("model_subcat_edit_", "").split("_")
    cat_id = int(parts[0])
    sub_id = int(parts[1])

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        sub = await repo.get_subcategory(sub_id)
        items = await repo.get_items_by_subcategory(sub_id)

    if not items:
        await safe_edit_text(
            callback,
            f"В подкатегории <b>{sub.name}</b> нет элементов!",
            reply_markup=get_admin_back_keyboard("model_cat_edit_menu")
        )
        return

    await state.update_data(selected_subcat_id=sub_id)
    await safe_edit_text(
        callback,
        f"<b>{sub.name}</b>\n\nВыберите элемент для редактирования:",
        reply_markup=get_model_items_list(items, cat_id, sub_id, "edit")
    )


@router.callback_query(F.data.startswith("model_item_edit_"))
async def model_edit_item_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    item_id = int(callback.data.replace("model_item_edit_", ""))

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        item = await repo.get_item(item_id)

    await state.update_data(item_id=item_id, old_name=item.name, old_prompt=item.prompt)
    await state.set_state(AdminModelCategoryStates.editing_item_name)

    await safe_edit_text(
        callback,
        f"<b>Редактировать: {item.name}</b>\n\n"
        f"Текущий промпт:\n<code>{item.prompt}</code>\n\n"
        "Введите <b>новое название</b> (рус):",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelCategoryStates.editing_item_name, F.text)
async def model_edit_item_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    await state.update_data(new_name=new_name)
    await state.set_state(AdminModelCategoryStates.editing_item_prompt)

    data = await state.get_data()
    await message.answer(
        f"Новое название: <b>{new_name}</b>\n\n"
        f"Текущий промпт:\n<code>{data['old_prompt']}</code>\n\n"
        "Введите <b>новый промпт</b> (англ):",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelCategoryStates.editing_item_prompt, F.text)
async def model_save_edited_item(message: Message, state: FSMContext):
    data = await state.get_data()
    item_id = data["item_id"]
    new_name = data["new_name"]
    new_prompt = message.text.strip()

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        await repo.update_item(item_id, new_name, new_prompt)

        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "edit_model_item",
            f"Отредактировано: {data['old_name']} → {new_name} (ID:{item_id})"
        )

    await state.clear()
    await message.answer(
        f"Элемент обновлён!\n\n"
        f"<b>{new_name}</b>\n"
        f"<code>{new_prompt}</code>",
        reply_markup=get_admin_back_keyboard("admin_model_types")
    )


@router.callback_query(F.data == "model_cat_delete_menu")
async def model_delete_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        categories = await repo.get_all_categories()

    if not categories:
        await safe_edit_text(
            callback,
            "Удалять нечего — категорий нет!",
            reply_markup=get_admin_back_keyboard("admin_model_types")
        )
        return

    await safe_edit_text(
        callback,
        "<b>Удаление</b>\n\nВыберите категорию:",
        reply_markup=get_model_categories_list(categories, "delete")
    )


@router.callback_query(F.data.startswith("model_cat_delete_"))
async def model_delete_select_category(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cat_id = int(callback.data.replace("model_cat_delete_", ""))

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        cat = await repo.get_category(cat_id)
        subcats = await repo.get_subcategories_by_category(cat_id)

    if not subcats:
        await safe_edit_text(
            callback,
            f"В категории <b>{cat.name}</b> нет подкатегорий!",
            reply_markup=get_admin_back_keyboard("model_cat_delete_menu")
        )
        return

    await state.update_data(selected_cat_id=cat_id)
    await safe_edit_text(
        callback,
        f"<b>{cat.name}</b>\n\nВыберите подкатегорию:",
        reply_markup=get_model_subcategories_list(subcats, cat_id, "delete")
    )


@router.callback_query(F.data.startswith("model_subcat_delete_"))
async def model_delete_select_subcategory(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("model_subcat_delete_", "").split("_")
    cat_id = int(parts[0])
    sub_id = int(parts[1])

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        sub = await repo.get_subcategory(sub_id)
        items = await repo.get_items_by_subcategory(sub_id)

    if not items:
        await safe_edit_text(
            callback,
            f"В подкатегории <b>{sub.name}</b> нет элементов!",
            reply_markup=get_admin_back_keyboard("model_cat_delete_menu")
        )
        return

    await state.update_data(selected_subcat_id=sub_id)
    await safe_edit_text(
        callback,
        f"<b>{sub.name}</b>\n\nВыберите элемент для удаления:",
        reply_markup=get_model_items_list(items, cat_id, sub_id, "delete")
    )


@router.callback_query(F.data.startswith("model_item_delete_"))
async def model_delete_item_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    item_id = int(callback.data.replace("model_item_delete_", ""))

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        item = await repo.get_item(item_id)

    await safe_edit_text(
        callback,
        f"<b>Удалить элемент?</b>\n\n{item.name}",
        reply_markup=get_confirm_delete_keyboard("model_item", str(item_id))
    )


@router.callback_query(F.data.startswith("confirm_delete_model_item_"))
async def model_delete_item_execute(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("confirm_delete_model_item_", ""))
    await callback.answer("Удалено")

    async with async_session_maker() as session:
        repo = ModelCategoryRepository(session)
        item = await repo.get_item(item_id)
        item_name = item.name

        await repo.delete_item(item_id)

        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "delete_model_item",
            f"Удалено: {item_name} (ID:{item_id})"
        )

    await state.clear()
    await safe_edit_text(
        callback,
        f"Элемент удалён:\n\n<b>{item_name}</b>",
        reply_markup=get_admin_back_keyboard("admin_model_types")
    )


@router.callback_query(F.data == "model_cat_cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отменено")
    await state.clear()
    await admin_model_categories_main(callback, state)