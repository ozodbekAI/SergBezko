# admin_normalize.py

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from handlers.admin import check_admin, safe_edit_text
from states import AdminNormalizePromptStates
from database import async_session_maker
from database.repositories import BotMessageRepository, AdminLogRepository

from admin_keyboards import (
    get_admin_normalize_menu,
    get_admin_back_keyboard,
)




router = Router()


@router.callback_query(F.data == "admin_normalize_prompts")
async def admin_normalize_prompts_menu(callback: CallbackQuery, state: FSMContext):
    """Asosiy normalize-prompt menyu."""
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return

    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        p1 = await msg_repo.get_message("normalize_prompt_step1")
        p2 = await msg_repo.get_message("normalize_prompt_step2_own")

    text1 = p1.text if p1 and p1.text else "❌ Не задан (используется дефолтный)"
    text2 = p2.text if p2 and p2.text else "❌ Не задан (используется дефолтный)"

    txt = (
        "👗 <b>Промпты нормализации фотомодели</b>\n\n"
        "1️⃣ <b>Промпт манекена (1-я фото)</b>\n"
        f"{text1}\n\n"
        "2️⃣ <b>Промпт для режима «Есть своя фотомодель» (2-я фото)</b>\n"
        f"{text2}\n\n"
        "<i>1-й промпт используется для обеих кнопок, только для первой фотографии.\n"
        "2-й промпт — только во втором шаге режима «Есть своя фотомодель».</i>"
    )

    await safe_edit_text(
        callback,
        txt,
        reply_markup=get_admin_normalize_menu()
    )


@router.callback_query(F.data == "admin_norm_edit_1")
async def admin_norm_edit_1(callback: CallbackQuery, state: FSMContext):
    """1-promptni tahrirlash (maneken uchun)."""
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return

    await callback.answer()
    await state.set_state(AdminNormalizePromptStates.entering_prompt1)

    await safe_edit_text(
        callback,
        "✏️ Введите <b>1-й промпт</b> для манекена (первая фотография):",
        reply_markup=get_admin_back_keyboard("admin_normalize_prompts")
    )


@router.callback_query(F.data == "admin_norm_edit_2")
async def admin_norm_edit_2(callback: CallbackQuery, state: FSMContext):
    """2-promptni tahrirlash (Есть своя фотомодель rejimi uchun)."""
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return

    await callback.answer()
    await state.set_state(AdminNormalizePromptStates.entering_prompt2)

    await safe_edit_text(
        callback,
        "✏️ Введите <b>2-й промпт</b> для режима «Есть своя фотомодель» (вторая фотография):",
        reply_markup=get_admin_back_keyboard("admin_normalize_prompts")
    )


@router.message(
    StateFilter(
        AdminNormalizePromptStates.entering_prompt1,
        AdminNormalizePromptStates.entering_prompt2
    ),
    F.text
)
async def admin_norm_prompt_saved(message: Message, state: FSMContext):
    """
    Bitta umumiy handler:
    - entering_prompt1 bo'lsa => normalize_prompt_step1
    - entering_prompt2 bo'lsa => normalize_prompt_step2_own
    """
    new_text = message.text.strip()
    current_state = await state.get_state()

    if current_state == AdminNormalizePromptStates.entering_prompt1.state:
        key = "normalize_prompt_step1"
        action = "update_normalize_prompt1"
        success_text = "✅ 1-й промпт для <b>манекена</b> успешно обновлен!"
    else:
        key = "normalize_prompt_step2_own"
        action = "update_normalize_prompt2"
        success_text = "✅ 2-й промпт для режима <b>«Есть своя фотомодель»</b> успешно обновлён!"

    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        await msg_repo.set_message(key, new_text)

        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            action,
            f"Updated {key}"
        )

    await state.clear()
    await message.answer(
        success_text,
        parse_mode="HTML",
        reply_markup=get_admin_normalize_menu()
    )
