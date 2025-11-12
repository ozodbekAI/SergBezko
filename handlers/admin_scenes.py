# handlers/admin_scenes.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import SceneRepository, AdminLogRepository
from states import AdminSceneStates
from admin_keyboards import (
    get_admin_back_keyboard, get_scene_main_menu, get_scene_groups_admin_list,
    get_scene_plans_admin_list, get_cancel_keyboard, get_confirm_delete_keyboard
)
import logging

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_PLANS = [
    "📷 Дальний план",
    "🧍 Средний план",
    "✋ Крупный план",
    "↔️ Боковой вид",
    "🔙 Вид со спины",
    "🎬 Динамический кадр"
]


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Edit failed: {e}")


@router.callback_query(F.data == "admin_scenes")
async def admin_scenes_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        groups = await repo.get_all_groups()

    text = "<b>📍 Управление сценами</b>\n\n<b>Структура:</b>\n\n"
    
    if groups:
        for group in groups:
            plans = await repo.get_plans_by_group(group.id)
            text += f"<b>{group.name}</b>\n"
            for plan in plans:
                text += f"   {plan.name} → <code>{plan.prompt[:40]}...</code>\n"
            text += "\n"
    else:
        text += "<i>Локаций пока нет</i>\n\n"

    await safe_edit_text(callback, text, get_scene_main_menu())


# ===== ДОБАВЛЕНИЕ ЛОКАЦИИ =====
@router.callback_query(F.data == "scene_add_location")
async def add_location_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminSceneStates.entering_group_name)
    await safe_edit_text(
        callback,
        "<b>➕ Добавление локации</b>\n\n"
        "Введите название локации:\n"
        "<i>Например: 👗 Бутик / Showroom</i>",
        get_cancel_keyboard("admin_scenes")
    )


@router.message(AdminSceneStates.entering_group_name, F.text)
async def add_location_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым!")
        return

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        group = await repo.add_group(name)
        await state.update_data(
            group_id=group.id,
            group_name=name,
            plans_to_add=DEFAULT_PLANS.copy(),
            current_plan_index=0
        )
        await state.set_state(AdminSceneStates.adding_default_plans)

    await message.answer(
        f"✅ Локация <b>{name}</b> создана!\n\n"
        f"Теперь введите промпт для <b>{DEFAULT_PLANS[0]}</b>:",
        reply_markup=get_cancel_keyboard("admin_scenes")
    )


@router.message(AdminSceneStates.adding_default_plans, F.text)
async def add_plan_prompt(message: Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("❌ Промпт не может быть пустым!")
        return

    data = await state.get_data()
    group_id = data["group_id"]
    plans = data["plans_to_add"]
    idx = data["current_plan_index"]
    plan_name = plans[idx]

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        await repo.add_plan_prompt(group_id, plan_name, prompt)
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_scene_plan",
            f"{plan_name} → {data['group_name']}"
        )

    next_idx = idx + 1
    if next_idx < len(plans):
        await state.update_data(current_plan_index=next_idx)
        await message.answer(
            f"✅ План <b>{plan_name}</b> добавлен!\n\n"
            f"Введите промпт для <b>{plans[next_idx]}</b>:",
            reply_markup=get_cancel_keyboard("admin_scenes")
        )
    else:
        await state.clear()
        await message.answer(
            f"🎉 Готово!\n\n"
            f"Локация: <b>{data['group_name']}</b>\n"
            f"Добавлено планов: {len(plans)}",
            reply_markup=get_admin_back_keyboard("admin_scenes")
        )


@router.callback_query(F.data == "scene_edit_prompt_menu")
async def edit_prompt_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        groups = await repo.get_all_groups()

    if not groups:
        await safe_edit_text(
            callback,
            "❌ Локаций нет!",
            get_admin_back_keyboard("admin_scenes")
        )
        return

    await safe_edit_text(
        callback,
        "<b>✏️ Редактирование промпта</b>\n\nВыберите локацию:",
        get_scene_groups_admin_list(groups, "edit")
    )


@router.callback_query(F.data.startswith("scene_admin_edit_group_"))
async def edit_select_group(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.replace("scene_admin_edit_group_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        group = await repo.get_group(group_id)
        plans = await repo.get_plans_by_group(group_id)

    if not plans:
        await safe_edit_text(
            callback,
            f"❌ В локации <b>{group.name}</b> нет планов!",
            get_admin_back_keyboard("scene_edit_prompt_menu")
        )
        return

    text = f"<b>{group.name}</b>\n\nВыберите план для редактирования:\n\n"
    for p in plans:
        text += f"• <b>{p.name}</b>\n  <code>{p.prompt[:60]}...</code>\n\n"

    await state.update_data(selected_group_id=group_id)
    await safe_edit_text(
        callback,
        text,
        get_scene_plans_admin_list(plans, group_id, "edit")
    )


@router.callback_query(F.data.startswith("scene_admin_edit_plan_"))
async def edit_plan_start(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.replace("scene_admin_edit_plan_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        plan = await repo.get_plan(plan_id)

    await state.update_data(plan_id=plan_id, plan_group_id=plan.group_id)
    await state.set_state(AdminSceneStates.entering_plan_prompt)

    await safe_edit_text(
        callback,
        f"<b>✏️ Редактирование: {plan.name}</b>\n\n"
        f"Текущий промпт:\n<code>{plan.prompt}</code>\n\n"
        f"Введите новый промпт:",
        get_cancel_keyboard("scene_edit_prompt_menu")
    )


@router.message(AdminSceneStates.entering_plan_prompt, F.text)
async def save_edited_prompt(message: Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("❌ Промпт не может быть пустым!")
        return

    data = await state.get_data()
    plan_id = data["plan_id"]

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        plan = await repo.update_plan_prompt(plan_id, prompt)
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "edit_scene_plan",
            f"{plan.name}"
        )

    await state.clear()
    await message.answer(
        f"✅ Промпт обновлён!\n\n"
        f"<b>{plan.name}</b>\n"
        f"<code>{prompt}</code>",
        reply_markup=get_admin_back_keyboard("admin_scenes")
    )


@router.callback_query(F.data == "scene_delete_prompt_menu")
async def delete_prompt_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        groups = await repo.get_all_groups()

    if not groups:
        await safe_edit_text(
            callback,
            "❌ Локаций нет!",
            get_admin_back_keyboard("admin_scenes")
        )
        return

    await safe_edit_text(
        callback,
        "<b>🗑 Удаление промпта</b>\n\nВыберите локацию:",
        get_scene_groups_admin_list(groups, "delete")
    )


@router.callback_query(F.data.startswith("scene_admin_delete_group_"))
async def delete_select_group(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.replace("scene_admin_delete_group_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        group = await repo.get_group(group_id)
        plans = await repo.get_plans_by_group(group_id)

    if not plans:
        await safe_edit_text(
            callback,
            f"❌ В локации <b>{group.name}</b> нет планов!",
            get_admin_back_keyboard("scene_delete_prompt_menu")
        )
        return

    text = f"<b>{group.name}</b>\n\nВыберите план для удаления:"
    await state.update_data(selected_group_id=group_id)
    await safe_edit_text(
        callback,
        text,
        get_scene_plans_admin_list(plans, group_id, "delete")
    )


@router.callback_query(F.data.startswith("scene_admin_delete_plan_"))
async def delete_plan_confirm(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.replace("scene_admin_delete_plan_", ""))
    await callback.answer()

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        plan = await repo.get_plan(plan_id)

    await safe_edit_text(
        callback,
        f"⚠️ <b>Удалить промпт?</b>\n\n{plan.name}",
        get_confirm_delete_keyboard("scene_plan", str(plan_id))
    )


@router.callback_query(F.data.startswith("confirm_delete_scene_plan_"))
async def delete_plan_execute(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.replace("confirm_delete_scene_plan_", ""))
    await callback.answer("✅ Удалено")

    async with async_session_maker() as session:
        repo = SceneRepository(session)
        plan = await repo.get_plan(plan_id)
        if not plan:
            await callback.message.edit_text("❌ План уже удалён или не существует.")
            return

        plan_name = plan.name
        await repo.delete_plan_prompt(plan_id)

        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "delete_scene_plan",
            f"Deleted: {plan_name} (ID: {plan_id})"
        )

    await safe_edit_text(
        callback,
        f"✅ Промпт удалён:\n\n<b>{plan_name}</b>",
        get_admin_back_keyboard("admin_scenes")
    )


@router.callback_query(F.data == "scene_cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отменено")
    await state.clear()
    await admin_scenes_main(callback, state)