from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from states import PhotoStates
from keyboards import (get_photo_menu, get_scene_groups, get_scenes_in_group,
                       get_pose_groups, get_poses_in_group, get_confirmation_keyboard, 
                       get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import (UserRepository, PoseElementRepository, 
                                   SceneElementRepository)
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()

# FIXED: safe_edit_text funksiyasini fayl boshiga ko'chirdim
async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    """Xavfsiz edit_text: Media bo'lsa delete + answer"""
    if callback.message.text is None:
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Delete failed: {e}")
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Edit failed: {e}")
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


@router.callback_query(F.data == "gen_photo")
async def photo_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    # Navigation stack qo'shish
    await state.update_data(nav_stack=["gen_photo"])  # FIXED: "main_generation" o'rniga "gen_photo"
    await safe_edit_text(callback, "📸 Фото\n\nВыберите режим обработки фото:", reply_markup=get_photo_menu())


@router.callback_query(F.data == "photo_scene")
async def photo_scene_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("photo_scene")
    
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="scene_change", nav_stack=nav_stack)
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button(nav_stack[-1]))


@router.callback_query(F.data == "photo_pose")
async def photo_pose_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("photo_pose")
    
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="pose_change", nav_stack=nav_stack)
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button(nav_stack[-1]))


@router.callback_query(F.data == "photo_custom")
async def photo_custom_scenario(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("photo_custom")
    
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="custom", nav_stack=nav_stack)
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button(nav_stack[-1]))


def get_back_button(current_step: str):
    """Navigatsiya stack bo'yicha back button yaratish – FIXED: InlineKeyboardBuilder ishlatildi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{current_step}"))
    return builder.as_markup()


@router.message(PhotoStates.waiting_for_photo, F.photo)
async def photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        nav_stack = data.get("nav_stack", [])
        await message.answer("❌ Пожалуйста, отправьте только ОДНО фото (не альбом).", 
                           reply_markup=get_back_button(nav_stack[-1] if nav_stack else "gen_photo"))
        return
    
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
    data = await state.get_data()
    mode = data["mode"]
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("photo_received")  # FIXED: Saqlanadi
    
    await state.update_data(photo_url=photo_url, nav_stack=nav_stack)
    
    if mode == "scene_change":
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_scenes = await scene_repo.get_all_scenes()
        
        groups = {}
        for scene_id, elements in all_scenes.items():
            if elements:
                group = elements[0].group
                if group not in groups:
                    groups[group] = []
                groups[group].append(scene_id)
        
        groups_list = [{"id": gid, "name": gid.title()} for gid in groups.keys()]
        # FIXED: Stack'ga "selecting_group" qo'shish
        nav_stack.append("selecting_group")
        await state.update_data(nav_stack=nav_stack)
        await message.answer("Выберите группу сцен:", reply_markup=get_scene_groups(groups_list))
        await state.set_state(PhotoStates.selecting_group)
        
    elif mode == "pose_change":
        async with async_session_maker() as session:
            pose_repo = PoseElementRepository(session)
            all_poses = await pose_repo.get_all_poses()
        
        groups = {}
        for pose_id, elements in all_poses.items():
            if elements:
                group = elements[0].group
                if group not in groups:
                    groups[group] = []
                groups[group].append(pose_id)
        
        groups_list = [{"id": gid, "name": gid.title()} for gid in groups.keys()]
        nav_stack.append("selecting_group")
        await state.update_data(nav_stack=nav_stack)
        await message.answer("Выберите группу поз:", reply_markup=get_pose_groups(groups_list))
        await state.set_state(PhotoStates.selecting_group)
        
    elif mode == "custom":
        nav_stack.append("entering_custom_prompt")
        await state.update_data(nav_stack=nav_stack)
        await message.answer("✏️ Введите свой промпт на русском или английском:", reply_markup=get_back_button("photo_received"))
        await state.set_state(PhotoStates.entering_custom_prompt)


@router.callback_query(F.data.startswith("back_"))
async def back_navigation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("back_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    if back_data == "back_to_generation":
        await state.clear()
        await safe_edit_text(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    

    if nav_stack and nav_stack[-1] == back_data:
        nav_stack.pop()
        await state.update_data(nav_stack=nav_stack)
    
    if not nav_stack:
        await state.clear()
        await safe_edit_text(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
        return
    
    current_state = await state.get_state()
    mode = data.get("mode")
    prev_step = nav_stack[-1] if nav_stack else None
    
    if prev_step == "gen_photo":
        await safe_edit_text(callback, "📸 Фото\n\nВыберите режим обработки фото:", reply_markup=get_photo_menu())
        return
    
    if prev_step in ["photo_scene", "photo_pose", "photo_custom"]:
        await state.set_state(PhotoStates.waiting_for_photo)
        if mode == "scene_change":
            await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button(prev_step))
        elif mode == "pose_change":
            await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button(prev_step))
        elif mode == "custom":
            await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button(prev_step))
        return
    
    if prev_step == "photo_received":
        await safe_edit_text(callback, "📸 Фото\n\nВыберите режим обработки фото:", reply_markup=get_photo_menu())
        return
    
    if prev_step == "selecting_group" and mode in ["scene_change", "pose_change"]:
        await state.set_state(PhotoStates.waiting_for_photo)
        if mode == "scene_change":
            await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button("photo_scene"))
        elif mode == "pose_change":
            await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button("photo_pose"))
        return
    
    if prev_step == "selecting_scene" and mode == "scene_change":
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_scenes = await scene_repo.get_all_scenes()
        
        groups = {}
        for scene_id, elements in all_scenes.items():
            if elements:
                group = elements[0].group
                if group not in groups:
                    groups[group] = []
                groups[group].append(scene_id)
        
        groups_list = [{"id": gid, "name": gid.title()} for gid in groups.keys()]
        await safe_edit_text(callback, "Выберите группу сцен:", reply_markup=get_scene_groups(groups_list))
        await state.set_state(PhotoStates.selecting_group)
        return
    
    if prev_step == "selecting_plan" and mode == "scene_change":
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_scenes = await scene_repo.get_all_scenes()
        
        group_scenes = {}
        for scene_id, elements in all_scenes.items():
            if elements and elements[0].group == group_id:
                group_scenes[scene_id] = elements
        
        scenes_list = [{"id": sid, "name": sid.replace("_", " ").title()} for sid in group_scenes.keys()]
        await safe_edit_text(callback, "Выберите сцену:", reply_markup=get_scenes_in_group(scenes_list, group_id))
        await state.set_state(PhotoStates.selecting_scene)
        return
    
    if prev_step == "selecting_element" and mode == "scene_change":
        data = await state.get_data()
        scene_id = data.get("selected_scene", "")
        builder = InlineKeyboardBuilder()
        plans = [
            ("far", "Дальний план"),
            ("medium", "Средний план"),
            ("close", "Крупный план"),
            ("side", "Боковой вид"),
            ("back", "Вид со спины"),
            ("motion", "Динамический кадр")
        ]
        for plan_id, plan_name in plans:
            builder.row(InlineKeyboardButton(text=plan_name, callback_data=f"plan_{plan_id}_{scene_id}"))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_scene"))
        
        text = f"🌆 <b>{scene_id.replace('_', ' ').title()}</b>\n\nВыберите план съёмки:"
        await safe_edit_text(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.set_state(PhotoStates.selecting_plan)
        return
    
    if prev_step == "selecting_pose" and mode == "pose_change":
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        async with async_session_maker() as session:
            pose_repo = PoseElementRepository(session)
            all_poses = await pose_repo.get_all_poses()
        
        group_poses = {}
        for pose_id, elements in all_poses.items():
            if elements and elements[0].group == group_id:
                group_poses[pose_id] = elements
        
        poses_list = [{"id": pid, "name": pid.replace("_", " ").title()} for pid in group_poses.keys()]
        await safe_edit_text(callback, "Выберите позу:", reply_markup=get_poses_in_group(poses_list, group_id))
        await state.set_state(PhotoStates.selecting_pose)
        return
    
    if prev_step == "selecting_pose_element" and mode == "pose_change":
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        async with async_session_maker() as session:
            pose_repo = PoseElementRepository(session)
            all_poses = await pose_repo.get_all_poses()
        
        group_poses = {}
        for pose_id, elements in all_poses.items():
            if elements and elements[0].group == group_id:
                group_poses[pose_id] = elements
        
        poses_list = [{"id": pid, "name": pid.replace("_", " ").title()} for pid in group_poses.keys()]
        await safe_edit_text(callback, "Выберите позу:", reply_markup=get_poses_in_group(poses_list, group_id))
        await state.set_state(PhotoStates.selecting_pose)
        return
    
    if prev_step == "entering_custom_prompt":
        await state.set_state(PhotoStates.waiting_for_photo)
        await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button("photo_custom"))
        return
    
    await safe_edit_text(callback, "Выберите тип генерации:", reply_markup=get_generation_menu())
    await state.clear()

@router.callback_query(PhotoStates.selecting_group, F.data.startswith("scene_group_"))  
async def select_photo_scene_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = callback.data.replace("scene_group_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_group_scene")  
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        all_scenes = await scene_repo.get_all_scenes()
    
    group_scenes = {}
    for scene_id, elements in all_scenes.items():
        if elements and elements[0].group == group_id:
            group_scenes[scene_id] = elements
    
    scenes_list = [{"id": sid, "name": sid.replace("_", " ").title()} for sid in group_scenes.keys()]
    
    await state.update_data(selected_group=group_id, group_scenes=group_scenes, nav_stack=nav_stack)
    await safe_edit_text(callback, "Выберите сцену:", reply_markup=get_scenes_in_group(scenes_list, group_id))
    await state.set_state(PhotoStates.selecting_scene)


@router.callback_query(PhotoStates.selecting_scene, F.data.startswith("scene_"))
async def select_photo_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data.startswith("back_"):
        await back_navigation(callback, state)
        return
    
    scene_id = callback.data.replace("scene_", "")
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        elements = await scene_repo.get_elements_by_scene(scene_id)
    
    if not elements:
        await callback.answer("❌ Нет элементов для этой сцены", show_alert=True)
        return
    
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    nav_stack.append("selecting_plan")  
    
    await state.update_data(
        selected_scene=scene_id,
        scene_elements=elements,
        selected_element_ids=[],
        selected_plan=None,
        nav_stack=nav_stack 
    )
    
    # Plans keyboard (o'zgarmasdan)
    builder = InlineKeyboardBuilder()
    plans = [
        ("far", "Дальний план"),
        ("medium", "Средний план"),
        ("close", "Крупный план"),
        ("side", "Боковой вид"),
        ("back", "Вид со спины"),
        ("motion", "Динамический кадр")
    ]
    for plan_id, plan_name in plans:
        builder.row(InlineKeyboardButton(text=plan_name, callback_data=f"plan_{plan_id}_{scene_id}"))
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_scene"))
    
    text = f"🌆 <b>{scene_id.replace('_', ' ').title()}</b>\n\nВыберите план съёмки:"
    await safe_edit_text(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(PhotoStates.selecting_plan)


@router.callback_query(PhotoStates.selecting_plan, F.data.startswith("plan_"))
async def select_scene_plan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data.startswith("back_"):
        await back_navigation(callback, state)
        return
    
    parts = callback.data.split("_", 2)
    plan_id = parts[1]
    scene_id = parts[2]
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        elements = await scene_repo.get_elements_by_scene(scene_id)
    
    await state.update_data(selected_plan=plan_id, scene_elements=elements, selected_element_ids=[])
    
    text = f"🌆 <b>{scene_id.replace('_', ' ').title()}</b> - <b>{plan_id.title()}</b>\n\nВыберите элементы сцены:\n\n"
    for elem in elements:
        prompt_field = f"prompt_{plan_id}"
        prompt = getattr(elem, prompt_field, elem.prompt_medium if hasattr(elem, 'prompt_medium') else "")
        text += f"• {elem.name} ({elem.element_type}) - <code>{prompt[:50]}...</code>\n"
    

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"⬜ {elem.name}",
            callback_data=f"scene_elem_{elem.id}_{plan_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data=f"scene_elem_done_{plan_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_scene"))
    
    await safe_edit_text(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(PhotoStates.selecting_element)


@router.callback_query(PhotoStates.selecting_element, F.data.startswith("scene_elem_"))
async def toggle_scene_element(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_")
    if parts[2] == "done":
        plan_id = parts[3] if len(parts) > 3 else None
        data = await state.get_data()
        selected_ids = data.get("selected_element_ids", [])
        
        if not selected_ids:
            await callback.answer("❌ Выберите хотя бы один элемент", show_alert=True)
            return
        
        cost = len(selected_ids) * config_loader.pricing["photo"]["scene_change"]
        await state.update_data(cost=cost, generation_type="selected_elements", selected_plan=plan_id)
        
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            has_balance = await user_repo.check_balance(callback.from_user.id, cost)
            if not has_balance:
                await safe_edit_text(callback, "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_to_generation())
                await state.clear()
                return
        
        await safe_edit_text(callback, f"Выбрано элементов: {len(selected_ids)}\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost))
        await state.set_state(PhotoStates.confirming)
        return
    
    elem_id = int(parts[2])  
    plan_id = parts[3] if len(parts) > 3 else None
    
    data = await state.get_data()
    selected_ids = data.get("selected_element_ids", [])
    
    if elem_id in selected_ids:
        selected_ids.remove(elem_id)
    else:
        selected_ids.append(elem_id)
    
    await state.update_data(selected_element_ids=selected_ids)

    elements = data["scene_elements"]
    scene_id = data["selected_scene"]
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        is_selected = elem.id in selected_ids
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if is_selected else '⬜'} {elem.name}",
            callback_data=f"scene_elem_{elem.id}_{plan_id or ''}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data=f"scene_elem_done_{plan_id or ''}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_plan"))
    
    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Reply markup edit failed: {e}")


@router.callback_query(PhotoStates.selecting_group, F.data.startswith("pose_group_"))
async def select_photo_pose_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = callback.data.replace("pose_group_", "")
    data = await state.get_data()
    nav_stack = data.get("nav_stack", [])
    
    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        all_poses = await pose_repo.get_all_poses()
    
    group_poses = {}
    for pose_id, elements in all_poses.items():
        if elements and elements[0].group == group_id:
            group_poses[pose_id] = elements
    
    poses_list = [{"id": pid, "name": pid.replace("_", " ").title()} for pid in group_poses.keys()]
    
    nav_stack.append("selecting_group_pose")
    await state.update_data(selected_group=group_id, group_poses=group_poses, nav_stack=nav_stack)
    await safe_edit_text(callback, "Выберите позу:", reply_markup=get_poses_in_group(poses_list, group_id))
    await state.set_state(PhotoStates.selecting_pose)


@router.callback_query(PhotoStates.selecting_pose, F.data.startswith("pose_"))
async def select_photo_pose(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data.startswith("back_"):
        await back_navigation(callback, state)
        return
    
    pose_id = callback.data.replace("pose_", "")
    
    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        elements = await pose_repo.get_elements_by_pose(pose_id)
    
    if not elements:
        await callback.answer("❌ Нет элементов для этой позы", show_alert=True)
        return
    
    await state.update_data(
        selected_pose=pose_id,
        pose_elements=elements,
        selected_element_ids=[]
    )
    
    text = f"🤸 <b>{pose_id.replace('_', ' ').title()}</b>\n\nВыберите элементы позы:\n\n"
    for elem in elements:
        text += f"• {elem.name} ({elem.element_type}) - <code>{elem.prompt[:50]}...</code>\n"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"⬜ {elem.name}",
            callback_data=f"pose_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="pose_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_group_pose"))
    
    await safe_edit_text(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(PhotoStates.selecting_pose_element)


@router.callback_query(PhotoStates.selecting_pose_element, F.data.startswith("pose_elem_"))
async def toggle_pose_element(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    if callback.data == "pose_elem_done":
        data = await state.get_data()
        selected_ids = data.get("selected_element_ids", [])
        
        if not selected_ids:
            await callback.answer("❌ Выберите хотя бы один элемент", show_alert=True)
            return
        
        cost = len(selected_ids) * config_loader.pricing["photo"]["pose_change"]
        await state.update_data(cost=cost, generation_type="selected_elements")
        
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            has_balance = await user_repo.check_balance(callback.from_user.id, cost)
            if not has_balance:
                await safe_edit_text(callback, "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'", reply_markup=get_back_to_generation())
                await state.clear()
                return
        
        await safe_edit_text(callback, f"Выбрано элементов: {len(selected_ids)}\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard(cost))
        await state.set_state(PhotoStates.confirming)
        return
    
    elem_id = int(callback.data.replace("pose_elem_", ""))
    data = await state.get_data()
    selected_ids = data.get("selected_element_ids", [])
    
    if elem_id in selected_ids:
        selected_ids.remove(elem_id)
    else:
        selected_ids.append(elem_id)
    
    await state.update_data(selected_element_ids=selected_ids)
    
    pose_id = data["selected_pose"]
    elements = data["pose_elements"]
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        is_selected = elem.id in selected_ids
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if is_selected else '⬜'} {elem.name}",
            callback_data=f"pose_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="pose_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_selecting_pose"))
    
    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Pose reply markup edit failed: {e}")


@router.message(PhotoStates.entering_custom_prompt, F.text)
async def photo_custom_prompt_received(message: Message, state: FSMContext):
    custom_prompt = message.text
    translated_prompt = await translator_service.translate_ru_to_en(custom_prompt)
    cost = config_loader.pricing["photo"]["custom_scenario"]
    await state.update_data(generation_type="custom", prompt=translated_prompt, cost=cost)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        has_balance = await user_repo.check_balance(message.from_user.id, cost)
        if not has_balance:
            await message.answer(
                "❌ Недостаточно кредитов на балансе.\n\nПополните баланс в разделе 'Мой кабинет.'",
                reply_markup=get_back_to_generation()
            )
            await state.clear()
            return
    
    await message.answer(
        f"Ваш промпт: {translated_prompt}\n\nБудет списано {cost} кредит.\n\nПродолжить?",
        reply_markup=get_confirmation_keyboard(cost)
    )
    await state.set_state(PhotoStates.confirming)


@router.callback_query(PhotoStates.confirming, F.data.startswith("confirm_"))
async def confirm_photo_generation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    photo_url = data["photo_url"]
    mode = data["mode"]
    cost = data["cost"]
    generation_type = data.get("generation_type")
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.update_balance(callback.from_user.id, -cost)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    
    await safe_edit_text(callback, "⏳ Генерация началась...")
    
    try:
        results = []
        if mode == "scene_change" and generation_type == "selected_elements":
            selected_ids = data["selected_element_ids"]
            scene_id = data["selected_scene"]
            plan_id = data.get("selected_plan", "medium")
            
            async with async_session_maker() as session:
                scene_repo = SceneElementRepository(session)
                all_elements = await scene_repo.get_elements_by_scene(scene_id)
            
            for elem in all_elements:
                if elem.id in selected_ids:
                    prompt_field = f"prompt_{plan_id}"
                    prompt = getattr(elem, prompt_field, elem.prompt_medium)
                    result = await kie_service.change_scene(photo_url, prompt)
                    result["element_name"] = f"{elem.name} ({plan_id.title()})"
                    results.append(result)
        
        elif mode == "pose_change" and generation_type == "selected_elements":
            selected_ids = data["selected_element_ids"]
            pose_id = data["selected_pose"]
            
            async with async_session_maker() as session:
                pose_repo = PoseElementRepository(session)
                all_elements = await pose_repo.get_elements_by_pose(pose_id)
            
            for elem in all_elements:
                if elem.id in selected_ids:
                    result = await kie_service.change_pose(photo_url, elem.prompt)
                    result["element_name"] = elem.name
                    results.append(result)
        
        elif mode == "custom":
            prompt = data["prompt"]
            result = await kie_service.custom_generation(photo_url, prompt)
            results.append(result)
        
        for i, result in enumerate(results, 1):
            if "image" in result:
                caption = result.get("element_name") or f"Результат {i}"
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
        logger.error(f"Photo generation error: {e}", exc_info=True)
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            await user_repo.update_balance(callback.from_user.id, cost)
        await callback.message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nКредиты возвращены на баланс.",
            reply_markup=get_back_to_generation()
        )
    
    await state.clear()


