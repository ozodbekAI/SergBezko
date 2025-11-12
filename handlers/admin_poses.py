from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import PoseRepository, AdminLogRepository
from states import AdminPoseStates
from admin_keyboards import (
    get_pose_main_menu, get_pose_groups_admin_list, get_pose_subgroups_admin_list,
    get_pose_prompts_admin_list, get_admin_back_keyboard, get_cancel_keyboard,
    get_confirm_delete_keyboard
)
import logging

logger = logging.getLogger(__name__)
router = Router(name="admin_poses")


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    try:
        if callback.message.text != text or callback.message.reply_markup != reply_markup:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Edit failed: {e}")


@router.callback_query(F.data == "admin_poses")
async def admin_poses_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        hierarchy = await pose_repo.get_full_hierarchy()
    
    total_groups = len(hierarchy)
    total_subgroups = sum(len(g["subgroups"]) for g in hierarchy.values())
    total_prompts = sum(
        len(sg["prompts"]) 
        for g in hierarchy.values() 
        for sg in g["subgroups"].values()
    )
    
    text = (
        f"🤸 <b>Управление позами</b>\n\n"
        f"📊 Статистика:\n"
        f"• Групп: {total_groups}\n"
        f"• Подгрупп: {total_subgroups}\n"
        f"• Промптов: {total_prompts}\n\n"
    )
    
    if hierarchy:
        text += "<b>Структура:</b>\n\n"
        for gid, g in hierarchy.items():
            text += f"<b>{g['name']}</b>\n"
            for sgid, sg in g["subgroups"].items():
                text += f"   ├── {sg['name']}\n"
                for p in sg["prompts"][:2]:
                    text += f"      └── {p['name']}\n"
                if len(sg["prompts"]) > 2:
                    text += f"      └── ...еще {len(sg['prompts']) - 2}\n"
            text += "\n"
    
    await safe_edit_text(callback, text, reply_markup=get_pose_main_menu())


@router.callback_query(F.data == "pose_add_main_group")
async def pose_add_group_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminPoseStates.entering_group_name)
    
    await safe_edit_text(
        callback,
        "➕ <b>Добавление группы</b>\n\n"
        "Введите название группы:\n"
        "<i>Например: 🧍 Стоя</i>",
        reply_markup=get_cancel_keyboard("admin_poses")
    )


@router.message(AdminPoseStates.entering_group_name, F.text)
async def pose_add_group_name(message: Message, state: FSMContext):
    group_name = message.text.strip()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.add_group(group_name)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_pose_group",
            f"Added group: {group.name} (ID: {group.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Группа добавлена!\n\n"
        f"Название: {group_name}\n"
        f"ID: {group.id}",
        reply_markup=get_admin_back_keyboard("admin_poses")
    )


@router.callback_query(F.data == "pose_add_main_subgroup")
async def pose_add_subgroup_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        groups = await pose_repo.get_all_groups()
    
    if not groups:
        await safe_edit_text(
            callback,
            "❌ Сначала добавьте хотя бы одну группу!",
            reply_markup=get_admin_back_keyboard("admin_poses")
        )
        return
    
    await state.set_state(AdminPoseStates.selecting_group)
    await safe_edit_text(
        callback,
        "➕ <b>Добавление подгруппы</b>\n\n"
        "Выберите группу:",
        reply_markup=get_pose_groups_admin_list(groups, "add_subgroup")
    )


@router.callback_query(AdminPoseStates.selecting_group, F.data.startswith("pose_admin_add_subgroup_group_"))
async def pose_select_group_for_subgroup(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pose_admin_add_subgroup_group_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.get_group(group_id)
    
    await state.update_data(group_id=group_id, group_name=group.name)
    await state.set_state(AdminPoseStates.entering_subgroup_name)
    
    await safe_edit_text(
        callback,
        f"Группа выбрана: <b>{group.name}</b>\n\n"
        f"Введите название подгруппы:\n"
        f"<i>Например: Возле стены</i>",
        reply_markup=get_cancel_keyboard("admin_poses")
    )


@router.message(AdminPoseStates.entering_subgroup_name, F.text)
async def pose_add_subgroup_name(message: Message, state: FSMContext):
    data = await state.get_data()
    group_id = data["group_id"]
    group_name = data["group_name"]
    subgroup_name = message.text.strip()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        subgroup = await pose_repo.add_subgroup(group_id, subgroup_name)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_pose_subgroup",
            f"Added subgroup: {subgroup.name} to {group_name} (ID: {subgroup.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Подгруппа добавлена!\n\n"
        f"Группа: {group_name}\n"
        f"Название: {subgroup_name}\n"
        f"ID: {subgroup.id}",
        reply_markup=get_admin_back_keyboard("admin_poses")
    )


@router.callback_query(F.data == "pose_add_main_prompt")
async def pose_add_prompt_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        groups = await pose_repo.get_all_groups()
    
    if not groups:
        await safe_edit_text(
            callback,
            "❌ Сначала добавьте группу и подгруппу!",
            reply_markup=get_admin_back_keyboard("admin_poses")
        )
        return
    
    await state.set_state(AdminPoseStates.selecting_group)
    await safe_edit_text(
        callback,
        "➕ <b>Добавление промпта</b>\n\n"
        "Выберите группу:",
        reply_markup=get_pose_groups_admin_list(groups, "add_prompt")
    )


@router.callback_query(AdminPoseStates.selecting_group, F.data.startswith("pose_admin_add_prompt_group_"))
async def pose_select_group_for_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pose_admin_add_prompt_group_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.get_group(group_id)
        subgroups = await pose_repo.get_subgroups_by_group(group_id)
    
    if not subgroups:
        await safe_edit_text(
            callback,
            f"❌ В группе <b>{group.name}</b> нет подгрупп!",
            reply_markup=get_admin_back_keyboard("admin_poses")
        )
        return
    
    await state.update_data(group_id=group_id, group_name=group.name)
    await state.set_state(AdminPoseStates.selecting_subgroup)
    
    await safe_edit_text(
        callback,
        f"Группа: <b>{group.name}</b>\n\n"
        f"Выберите подгруппу:",
        reply_markup=get_pose_subgroups_admin_list(subgroups, group_id, "add_prompt")
    )


@router.callback_query(AdminPoseStates.selecting_subgroup, F.data.startswith("pose_admin_add_prompt_subgroup_"))
async def pose_select_subgroup_for_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("pose_admin_add_prompt_subgroup_", "").split("_")
    group_id = int(parts[0])
    subgroup_id = int(parts[1])
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.get_group(group_id)
        subgroup = await pose_repo.get_subgroup(subgroup_id)
    
    await state.update_data(
        group_id=group_id,
        group_name=group.name,
        subgroup_id=subgroup_id,
        subgroup_name=subgroup.name
    )
    await state.set_state(AdminPoseStates.entering_prompt_name)
    
    await safe_edit_text(
        callback,
        f"Группа: <b>{group.name}</b>\n"
        f"Подгруппа: <b>{subgroup.name}</b>\n\n"
        f"Введите название промпта (рус.):\n"
        f"<i>Например: Руки в карманах</i>",
        reply_markup=get_cancel_keyboard("admin_poses")
    )


@router.message(AdminPoseStates.entering_prompt_name, F.text)
async def pose_add_prompt_name(message: Message, state: FSMContext):
    prompt_name = message.text.strip()
    data = await state.get_data()
    
    await state.update_data(prompt_name=prompt_name)
    await state.set_state(AdminPoseStates.entering_prompt_text)
    
    await message.answer(
        f"Группа: <b>{data['group_name']}</b>\n"
        f"Подгруппа: <b>{data['subgroup_name']}</b>\n"
        f"Название: <b>{prompt_name}</b>\n\n"
        f"Теперь введите сам промпт (англ.):\n"
        f"<i>Например: standing near wall, hands in pockets, casual pose</i>",
        reply_markup=get_cancel_keyboard("admin_poses")
    )


@router.message(AdminPoseStates.entering_prompt_text, F.text)
async def pose_add_prompt_text(message: Message, state: FSMContext):
    data = await state.get_data()
    subgroup_id = data["subgroup_id"]
    prompt_name = data["prompt_name"]
    prompt_text = message.text.strip()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        prompt = await pose_repo.add_prompt(subgroup_id, prompt_name, prompt_text)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_pose_prompt",
            f"Added prompt: {prompt.name} (ID: {prompt.id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Промпт добавлен!\n\n"
        f"Группа: {data['group_name']}\n"
        f"Подгруппа: {data['subgroup_name']}\n"
        f"Название: {prompt_name}\n"
        f"Промпт: <code>{prompt_text}</code>\n"
        f"ID: {prompt.id}",
        reply_markup=get_admin_back_keyboard("admin_poses")
    )


@router.callback_query(F.data == "pose_edit_main_menu")
async def pose_edit_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        groups = await pose_repo.get_all_groups()
    
    if not groups:
        await safe_edit_text(
            callback,
            "❌ Групп для редактирования нет!",
            reply_markup=get_admin_back_keyboard("admin_poses")
        )
        return
    
    await safe_edit_text(
        callback,
        "✏️ <b>Редактирование</b>\n\nВыберите группу:",
        reply_markup=get_pose_groups_admin_list(groups, "edit")
    )


@router.callback_query(F.data.startswith("pose_admin_edit_group_"))
async def pose_edit_select_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pose_admin_edit_group_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.get_group(group_id)
        subgroups = await pose_repo.get_subgroups_by_group(group_id)
    
    if not subgroups:
        await safe_edit_text(
            callback,
            f"❌ В группе <b>{group.name}</b> нет подгрупп!",
            get_admin_back_keyboard("pose_edit_main_menu")
        )
        return
    
    await state.update_data(selected_group_id=group_id)
    await safe_edit_text(
        callback,
        f"<b>{group.name}</b>\n\nВыберите подгруппу:",
        get_pose_subgroups_admin_list(subgroups, group_id, "edit")
    )


@router.callback_query(F.data.startswith("pose_admin_edit_subgroup_"))
async def pose_edit_select_subgroup(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("pose_admin_edit_subgroup_", "").split("_")
    group_id = int(parts[0])
    subgroup_id = int(parts[1])
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        subgroup = await pose_repo.get_subgroup(subgroup_id)
        prompts = await pose_repo.get_prompts_by_subgroup(subgroup_id)
    
    if not prompts:
        await safe_edit_text(
            callback,
            f"❌ В подгруппе <b>{subgroup.name}</b> нет промптов!",
            get_admin_back_keyboard("pose_edit_main_menu")
        )
        return
    
    text = f"<b>{subgroup.name}</b>\n\nВыберите промпт для редактирования:\n\n"
    for p in prompts:
        text += f"• <b>{p.name}</b>\n  <code>{p.prompt[:60]}...</code>\n\n"
    
    await state.update_data(selected_subgroup_id=subgroup_id)
    await safe_edit_text(
        callback,
        text,
        get_pose_prompts_admin_list(prompts, group_id, subgroup_id, "edit")
    )


@router.callback_query(F.data.startswith("pose_admin_edit_prompt_"))
async def pose_edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    prompt_id = int(callback.data.replace("pose_admin_edit_prompt_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        prompt = await pose_repo.get_prompt(prompt_id)
    
    await state.update_data(prompt_id=prompt_id)
    await state.set_state(AdminPoseStates.editing_prompt_text)
    
    await safe_edit_text(
        callback,
        f"<b>✏️ Редактирование: {prompt.name}</b>\n\n"
        f"Текущий промпт:\n<code>{prompt.prompt}</code>\n\n"
        f"Введите новый промпт:",
        get_cancel_keyboard("admin_poses")
    )


@router.message(AdminPoseStates.editing_prompt_text, F.text)
async def pose_save_edited_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    prompt_id = data["prompt_id"]
    new_prompt = message.text.strip()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        prompt = await pose_repo.get_prompt(prompt_id)
        old_name = prompt.name
        
        await pose_repo.update_prompt(prompt_id, old_name, new_prompt)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "edit_pose_prompt",
            f"Edited: {old_name} (ID: {prompt_id})"
        )
    
    await state.clear()
    await message.answer(
        f"✅ Промпт обновлён!\n\n"
        f"<b>{old_name}</b>\n"
        f"<code>{new_prompt}</code>",
        reply_markup=get_admin_back_keyboard("admin_poses")
    )


@router.callback_query(F.data == "pose_delete_main_menu")
async def pose_delete_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        groups = await pose_repo.get_all_groups()
    
    if not groups:
        await safe_edit_text(
            callback,
            "❌ Групп для удаления нет!",
            reply_markup=get_admin_back_keyboard("admin_poses")
        )
        return
    
    await safe_edit_text(
        callback,
        "🗑 <b>Удаление</b>\n\nВыберите группу:",
        reply_markup=get_pose_groups_admin_list(groups, "delete")
    )


@router.callback_query(F.data.startswith("pose_admin_delete_group_"))
async def pose_delete_select_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.replace("pose_admin_delete_group_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        group = await pose_repo.get_group(group_id)
        subgroups = await pose_repo.get_subgroups_by_group(group_id)
    
    if not subgroups:
        await safe_edit_text(
            callback,
            f"❌ В группе <b>{group.name}</b> нет подгрупп!",
            get_admin_back_keyboard("pose_delete_main_menu")
        )
        return
    
    await state.update_data(selected_group_id=group_id)
    await safe_edit_text(
        callback,
        f"<b>{group.name}</b>\n\nВыберите подгруппу:",
        get_pose_subgroups_admin_list(subgroups, group_id, "delete")
    )


@router.callback_query(F.data.startswith("pose_admin_delete_subgroup_"))
async def pose_delete_select_subgroup(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("pose_admin_delete_subgroup_", "").split("_")
    group_id = int(parts[0])
    subgroup_id = int(parts[1])
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        subgroup = await pose_repo.get_subgroup(subgroup_id)
        prompts = await pose_repo.get_prompts_by_subgroup(subgroup_id)
    
    if not prompts:
        await safe_edit_text(
            callback,
            f"❌ В подгруппе <b>{subgroup.name}</b> нет промптов!",
            get_admin_back_keyboard("pose_delete_main_menu")
        )
        return
    
    text = f"<b>{subgroup.name}</b>\n\nВыберите промпт для удаления:"
    await state.update_data(selected_subgroup_id=subgroup_id)
    await safe_edit_text(
        callback,
        text,
        get_pose_prompts_admin_list(prompts, group_id, subgroup_id, "delete")
    )


@router.callback_query(F.data.startswith("pose_admin_delete_prompt_"))
async def pose_delete_prompt_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    prompt_id = int(callback.data.replace("pose_admin_delete_prompt_", ""))
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        prompt = await pose_repo.get_prompt(prompt_id)
    
    await safe_edit_text(
        callback,
        f"⚠️ <b>Удалить промпт?</b>\n\n{prompt.name}",
        get_confirm_delete_keyboard("pose_prompt", str(prompt_id))
    )


@router.callback_query(F.data.startswith("confirm_delete_pose_prompt_"))
async def pose_delete_prompt_execute(callback: CallbackQuery, state: FSMContext):
    prompt_id = int(callback.data.replace("confirm_delete_pose_prompt_", ""))
    await callback.answer("✅ Удалено")
    
    async with async_session_maker() as session:
        pose_repo = PoseRepository(session)
        prompt = await pose_repo.get_prompt(prompt_id)
        prompt_name = prompt.name
        
        await pose_repo.delete_prompt(prompt_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "delete_pose_prompt",
            f"Deleted: {prompt_name} (ID: {prompt_id})"
        )
    
    await state.clear()
    await safe_edit_text(
        callback,
        f"✅ Промпт удалён:\n\n<b>{prompt_name}</b>",
        get_admin_back_keyboard("admin_poses")
    )


@router.callback_query(F.data == "pose_cancel_action")
async def cancel_pose_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отменено")
    await state.clear()
    await admin_poses_main(callback, state)