from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import ModelTypeRepository, AdminLogRepository
from states import AdminModelTypeStates
from admin_keyboards import (
    get_model_type_main_menu, get_model_types_list,
    get_admin_back_keyboard, get_cancel_keyboard,
    get_confirm_delete_keyboard
)
import logging

logger = logging.getLogger(__name__)

router = Router(name="admin_model_types")


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if callback.message.text != text or callback.message.reply_markup != reply_markup:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Edit failed: {e}")



@router.callback_query(F.data == "admin_model_types")
async def admin_model_types_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_types = await model_type_repo.get_all()
    
    text = (
        f"👤 <b>Управление типами моделей</b>\n\n"
        f"📊 Всего типов: {len(model_types)}\n\n"
        f"Выберите действие:"
    )
    
    await safe_edit_text(callback, text, reply_markup=get_model_type_main_menu())


@router.callback_query(F.data == "model_type_view_all")
async def model_type_view_all(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_types = await model_type_repo.get_all()
    
    if not model_types:
        await safe_edit_text(
            callback,
            "❌ Типов моделей пока нет. Добавьте первый тип!",
            reply_markup=get_admin_back_keyboard("admin_model_types")
        )
        return
    
    text = "👤 <b>Все типы моделей:</b>\n\n"
    for mt in model_types:
        text += f"<b>{mt.id}. {mt.name}</b>\n"
        text += f"  <code>{mt.prompt}</code>\n\n"
    
    await safe_edit_text(
        callback,
        text,
        reply_markup=get_model_types_list(model_types, "edit")
    )



@router.callback_query(F.data == "model_type_add")
async def model_type_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminModelTypeStates.entering_name)
    
    await safe_edit_text(
        callback,
        "➕ <b>Добавление типа модели</b>\n\n"
        "Введите название типа (рус.):\n"
        "<i>Например: Брюнетка</i>",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelTypeStates.entering_name, F.text)
async def model_type_add_name(message: Message, state: FSMContext):
    name = message.text.strip()
    
    await state.update_data(name=name)
    await state.set_state(AdminModelTypeStates.entering_prompt)
    
    await message.answer(
        f"Название: <b>{name}</b>\n\n"
        f"Теперь введите промпт (англ.):\n"
        f"<i>Например: A brunette woman model</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelTypeStates.entering_prompt, F.text)
async def model_type_add_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    prompt = message.text.strip()
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_type = await model_type_repo.add(name, prompt)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_model_type",
            f"Added model type: {model_type.name} (ID: {model_type.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Тип модели добавлен!\n\n"
        f"ID: {model_type.id}\n"
        f"Название: {name}\n"
        f"Промпт: <code>{prompt}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard("admin_model_types")
    )


@router.callback_query(F.data.startswith("model_type_edit_"))
async def model_type_edit_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    model_type_id = int(callback.data.replace("model_type_edit_", ""))
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_type = await model_type_repo.get_by_id(model_type_id)
    
    if not model_type:
        await callback.answer("❌ Тип не найден", show_alert=True)
        return
    
    await state.update_data(model_type_id=model_type_id)
    await state.set_state(AdminModelTypeStates.entering_name)
    
    await safe_edit_text(
        callback,
        f"✏️ <b>Редактирование типа модели</b>\n\n"
        f"Текущее название: <b>{model_type.name}</b>\n"
        f"Текущий промпт: <code>{model_type.prompt}</code>\n\n"
        f"Введите новое название:",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelTypeStates.entering_name, F.text)
async def model_type_edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    
    if "model_type_id" not in data:
        await model_type_add_name(message, state)
        return
    
    name = message.text.strip()
    
    await state.update_data(name=name)
    await state.set_state(AdminModelTypeStates.entering_prompt)
    
    await message.answer(
        f"Название: <b>{name}</b>\n\n"
        f"Теперь введите новый промпт:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("admin_model_types")
    )


@router.message(AdminModelTypeStates.entering_prompt, F.text)
async def model_type_edit_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    
    if "model_type_id" not in data:
        await model_type_add_prompt(message, state)
        return
    
    model_type_id = data["model_type_id"]
    name = data["name"]
    prompt = message.text.strip()
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_type = await model_type_repo.update(model_type_id, name, prompt)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "update_model_type",
            f"Updated model type: {model_type.name} (ID: {model_type.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Тип модели обновлен!\n\n"
        f"ID: {model_type.id}\n"
        f"Название: {name}\n"
        f"Промпт: <code>{prompt}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard("admin_model_types")
    )


@router.callback_query(F.data == "model_type_delete_menu")
async def model_type_delete_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_types = await model_type_repo.get_all()
    
    if not model_types:
        await safe_edit_text(
            callback,
            "❌ Типов для удаления нет!",
            reply_markup=get_admin_back_keyboard("admin_model_types")
        )
        return
    
    await safe_edit_text(
        callback,
        "🗑 <b>Удаление типа модели</b>\n\n"
        "Выберите тип для удаления:",
        reply_markup=get_model_types_list(model_types, "delete")
    )


@router.callback_query(F.data.startswith("model_type_delete_"))
async def model_type_delete_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    model_type_id = int(callback.data.replace("model_type_delete_", ""))
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_type = await model_type_repo.get_by_id(model_type_id)
    
    if not model_type:
        await callback.answer("❌ Тип не найден", show_alert=True)
        return
    
    await safe_edit_text(
        callback,
        f"⚠️ <b>Подтвердите удаление</b>\n\n"
        f"Тип: {model_type.name}\n"
        f"Промпт: <code>{model_type.prompt}</code>",
        reply_markup=get_confirm_delete_keyboard("model_type", str(model_type_id))
    )


@router.callback_query(F.data.startswith("confirm_delete_model_type_"))
async def model_type_delete_execute(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Удаляем...")
    model_type_id = int(callback.data.replace("confirm_delete_model_type_", ""))
    
    async with async_session_maker() as session:
        model_type_repo = ModelTypeRepository(session)
        model_type = await model_type_repo.get_by_id(model_type_id)
        model_type_name = model_type.name
        
        await model_type_repo.delete(model_type_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "delete_model_type",
            f"Deleted model type: {model_type_name} (ID: {model_type_id})"
        )
    
    await state.clear()
    await safe_edit_text(
        callback,
        f"✅ Тип модели <b>{model_type_name}</b> удален!",
        reply_markup=get_admin_back_keyboard("admin_model_types")
    )



@router.callback_query(F.data == "cancel_model_type_action")
async def cancel_model_type_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Отменено")
    await state.clear()
    await admin_model_types_main(callback, state)