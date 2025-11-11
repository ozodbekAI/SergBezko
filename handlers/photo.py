from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from states import PhotoStates
from keyboards import (get_back_button_photo, get_photo_menu, get_scene_groups, get_scenes_in_group,
                       get_pose_groups, get_poses_in_group, get_confirmation_keyboard_photo, 
                       get_repeat_button, get_back_to_generation, get_generation_menu)
from database import async_session_maker
from database.repositories import (UserRepository, PoseElementRepository, 
                                   SceneElementRepository)
from services.config_loader import config_loader
from services.kie_service import kie_service
from services.translator import translator_service
from config import settings
import logging

from utils.photo import get_photo_url_from_message

logger = logging.getLogger(__name__)
router = Router()


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


def get_back_button(current_step: str):
    """PHOTO MODULI ICHIDA - local funksiya"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"photo_back_{current_step}"))
    return builder.as_markup()


@router.callback_query(F.data == "gen_photo")
async def photo_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await safe_edit_text(callback, "📸 Фото\n\nВыберите режим обработки фото:", reply_markup=get_photo_menu())


@router.callback_query(F.data == "photo_scene")
async def photo_scene_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="scene_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены сцены.", reply_markup=get_back_button("photo_scene"))


@router.callback_query(F.data == "photo_pose")
async def photo_pose_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="pose_change")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для смены позы.", reply_markup=get_back_button("photo_pose"))


@router.callback_query(F.data == "photo_custom")
async def photo_custom_scenario(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(mode="custom")
    await safe_edit_text(callback, "📸 Отправьте ОДНО фото для обработки.", reply_markup=get_back_button("photo_custom"))


@router.message(PhotoStates.waiting_for_photo, F.photo | F.document)
async def photo_received(message: Message, state: FSMContext):
    if message.media_group_id:
        await message.answer("❌ Пожалуйста, отправьте только ОДНО фото (не альбом).", 
                           reply_markup=get_back_button("gen_photo"))
        return
    
    try:
        photo_url = await get_photo_url_from_message(message)
    except ValueError as ve:
        await message.answer(str(ve), reply_markup=get_back_button("gen_photo"))
        return
    except Exception as e:
        logger.error(f"Photo processing error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке фото. Попробуйте другое фото.", 
                           reply_markup=get_back_button("gen_photo"))
        return

    data = await state.get_data()
    mode = data["mode"]
    
    await state.update_data(photo_url=photo_url)
    
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
        await state.set_state(PhotoStates.selecting_group)
        
        # FIXED: back button with photo_received
        builder = InlineKeyboardBuilder()
        for group in groups_list:
            builder.row(InlineKeyboardButton(text=group["name"], callback_data=f"scene_group_{group['id']}"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))
        
        await message.answer("Выберите группу сцен:", reply_markup=builder.as_markup())
        
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
        await state.set_state(PhotoStates.selecting_group)
        
        # FIXED: back button with photo_received
        builder = InlineKeyboardBuilder()
        for group in groups_list:
            builder.row(InlineKeyboardButton(
                text=group["name"], 
                callback_data=f"pose_group_{group['id']}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))
        
        await message.answer("Выберите группу поз:", reply_markup=builder.as_markup())
        
    elif mode == "custom":
        await message.answer("✏️ Введите свой промпт на русском или английском:", reply_markup=get_back_button("photo_received"))
        await state.set_state(PhotoStates.entering_custom_prompt)


@router.callback_query(F.data.startswith("photo_back_"))
async def back_navigation_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    back_data = callback.data.replace("photo_back_", "")
    
    if back_data == "gen_photo":
        await state.clear()
        await safe_edit_text(callback,
            "Выберите тип генерации:",
            reply_markup=get_generation_menu()
        )
        return
    
    if back_data in ["photo_scene", "photo_pose", "photo_custom"]:
        await state.clear()
        await safe_edit_text(callback,
            "📸 Фото\n\nВыберите режим обработки фото:",
            reply_markup=get_photo_menu()
        )
        return
    
    if back_data == "photo_received":
        # FIXED: Photo yuborilgandan keyin - photo yuborish holatiga qaytish
        data = await state.get_data()
        mode = data.get("mode")
        
        await state.set_state(PhotoStates.waiting_for_photo)
        
        if mode == "scene_change":
            await safe_edit_text(callback,
                "📸 Отправьте ОДНО фото для смены сцены.",
                reply_markup=get_back_button("photo_scene")
            )
        elif mode == "pose_change":
            await safe_edit_text(callback,
                "📸 Отправьте ОДНО фото для смены позы.",
                reply_markup=get_back_button("photo_pose")
            )
        else:
            await safe_edit_text(callback,
                "📸 Отправьте ОДНО фото для обработки.",
                reply_markup=get_back_button("photo_custom")
            )
        return
    
    if back_data in ["selecting_group", "selecting_group_scene", "selecting_group_pose", "selecting_scene_groups"]:
        # Group tanlashdan - photo yuborishga qaytish
        data = await state.get_data()
        mode = data.get("mode")
        
        await state.set_state(PhotoStates.waiting_for_photo)
        
        if mode == "scene_change":
            await safe_edit_text(callback,
                "📸 Отправьте ОДНО фото для смены сцены.",
                reply_markup=get_back_button("photo_scene")
            )
        else:  # pose_change
            await safe_edit_text(callback,
                "📸 Отправьте ОДНО фото для смены позы.",
                reply_markup=get_back_button("photo_pose")
            )
        return
    
    if back_data == "selecting_scene":
        # Scene tanlashdan - group tanlashga
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_scenes = await scene_repo.get_all_scenes()
        
        groups = {}
        for scene_id, elements in all_scenes.items():
            if elements:
                group = elements[0].group
                if group not in groups:
                    groups[group] = []
        
        groups_list = [{"id": gid, "name": gid.title()} for gid in groups.keys()]
        
        await state.set_state(PhotoStates.selecting_group)
        
        builder = InlineKeyboardBuilder()
        for group in groups_list:
            builder.row(InlineKeyboardButton(text=group["name"], callback_data=f"scene_group_{group['id']}"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))
        
        await safe_edit_text(callback,
            "Выберите группу сцен:",
            reply_markup=builder.as_markup()
        )
        return
    
    if back_data == "selecting_plan":
        # Plan tanlashdan - scene tanlashga
        data = await state.get_data()
        group_id = data.get("selected_group", "")
        
        async with async_session_maker() as session:
            scene_repo = SceneElementRepository(session)
            all_scenes = await scene_repo.get_all_scenes()
        
        group_scenes = {sid: els for sid, els in all_scenes.items() 
                       if els and els[0].group == group_id}
        
        scenes_list = [{"id": sid, "name": sid.replace("_", " ").title()} 
                      for sid in group_scenes.keys()]
        
        await state.set_state(PhotoStates.selecting_scene)
        await safe_edit_text(callback,
            "Выберите сцену:",
            reply_markup=get_scenes_in_group(scenes_list, group_id)
        )
        return
    
    if back_data in ["selecting_pose", "selecting_group_pose"]:
        # Pose tanlashdan - group tanlashga
        async with async_session_maker() as session:
            pose_repo = PoseElementRepository(session)
            all_poses = await pose_repo.get_all_poses()
        
        groups = {}
        for pose_id, elements in all_poses.items():
            if elements:
                group = elements[0].group
                if group not in groups:
                    groups[group] = []
        
        groups_list = [{"id": gid, "name": gid.title()} for gid in groups.keys()]
        
        await state.set_state(PhotoStates.selecting_group)
        
        # FIXED: back button with photo_received
        builder = InlineKeyboardBuilder()
        for group in groups_list:
            builder.row(InlineKeyboardButton(
                text=group["name"], 
                callback_data=f"pose_group_{group['id']}"
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_photo_received"))
        
        await safe_edit_text(callback,
            "Выберите группу поз:",
            reply_markup=builder.as_markup()
        )
        return
    
    if back_data == "entering_custom_prompt":
        await state.set_state(PhotoStates.waiting_for_photo)
        await safe_edit_text(callback,
            "📸 Отправьте ОДНО фото для обработки.",
            reply_markup=get_back_button("photo_custom")
        )
        return


@router.callback_query(PhotoStates.selecting_group, F.data.startswith("scene_group_"))
async def select_scene_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = callback.data.replace("scene_group_", "")
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        all_scenes = await scene_repo.get_all_scenes()
    
    group_scenes = {sid: els for sid, els in all_scenes.items() 
                   if els and els[0].group == group_id}
    
    scenes_list = [{"id": sid, "name": sid.replace("_", " ").title()} 
                  for sid in group_scenes.keys()]
    
    await state.update_data(selected_group=group_id)
    await state.set_state(PhotoStates.selecting_scene)
    
    keyboard = []
    for scene in scenes_list:
        keyboard.append([InlineKeyboardButton(
            text=scene["name"], 
            callback_data=f"scene_{scene['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="✅ Все сцены группы", 
        callback_data=f"scene_all_{group_id}"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data="photo_back_selecting_scene"
    )])
    
    await safe_edit_text(callback, "Выберите сцену:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(PhotoStates.selecting_scene, F.data.startswith("scene_"))
async def select_photo_scene(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    scene_id = callback.data.replace("scene_", "")
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        elements = await scene_repo.get_elements_by_scene(scene_id)
    
    if not elements:
        await callback.answer("❌ Нет элементов для этой сцены", show_alert=True)
        return
    
    await state.update_data(
        selected_scene=scene_id,
        scene_elements=elements,
        selected_element_ids=[],
        selected_plan=None
    )
    
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
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_scene"))
    
    text = f"🌆 <b>{scene_id.replace('_', ' ').title()}</b>\n\nВыберите план съёмки:"
    await safe_edit_text(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(PhotoStates.selecting_plan)


@router.callback_query(PhotoStates.selecting_plan, F.data.startswith("plan_"))
async def select_scene_plan(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

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
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"⬜ {elem.name}",
            callback_data=f"scene_elem_{elem.id}_{plan_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data=f"scene_elem_done_{plan_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_plan"))
    
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
        
        await safe_edit_text(callback, f"Выбрано элементов: {len(selected_ids)}\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard_photo(cost, "selecting_element"))
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
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        is_selected = elem.id in selected_ids
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if is_selected else '⬜'} {elem.name}",
            callback_data=f"scene_elem_{elem.id}_{plan_id or ''}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data=f"scene_elem_done_{plan_id or ''}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_plan"))
    
    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Reply markup edit failed: {e}")


@router.callback_query(PhotoStates.selecting_group, F.data.startswith("pose_group_"))
async def select_photo_pose_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = callback.data.replace("pose_group_", "")
    
    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        all_poses = await pose_repo.get_all_poses()
    
    group_poses = {}
    for pose_id, elements in all_poses.items():
        if elements and elements[0].group == group_id:
            group_poses[pose_id] = elements
    
    poses_list = [{"id": pid, "name": pid.replace("_", " ").title()} for pid in group_poses.keys()]
    
    await state.update_data(selected_group=group_id, group_poses=group_poses)
    await state.set_state(PhotoStates.selecting_pose)
    
    # FIXED: back button
    builder = InlineKeyboardBuilder()
    for pose in poses_list:
        builder.row(InlineKeyboardButton(
            text=pose["name"],
            callback_data=f"pose_{pose['id']}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="✅ Все позы группы", 
        callback_data=f"pose_all_{group_id}"
    ))
    
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", 
        callback_data="photo_back_selecting_group_pose"
    ))
    
    await safe_edit_text(callback, "Выберите позу:", reply_markup=builder.as_markup())


@router.callback_query(PhotoStates.selecting_pose, F.data.startswith("pose_"))
async def select_photo_pose(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
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
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        builder.row(InlineKeyboardButton(
            text=f"⬜ {elem.name}",
            callback_data=f"pose_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="pose_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_group_pose"))
    
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
        
        await safe_edit_text(callback, f"Выбрано элементов: {len(selected_ids)}\nБудет списано {cost} кредитов.\n\nПродолжить?", reply_markup=get_confirmation_keyboard_photo(cost, "selecting_pose_element"))
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
    
    elements = data["pose_elements"]
    
    builder = InlineKeyboardBuilder()
    for elem in elements:
        is_selected = elem.id in selected_ids
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if is_selected else '⬜'} {elem.name}",
            callback_data=f"pose_elem_{elem.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="✅ Продолжить", callback_data="pose_elem_done"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="photo_back_selecting_pose"))
    
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
        reply_markup=get_confirmation_keyboard_photo(cost, "entering_custom_prompt")
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
    await state.update_data(last_generation={
        "type": "photo",
        "photo_url": photo_url,
        "mode": mode,
        "cost": cost,
        "generation_type": generation_type,
        "selected_element_ids": data.get("selected_element_ids", []),
        "selected_scene": data.get("selected_scene"),
        "selected_plan": data.get("selected_plan"),
        "selected_pose": data.get("selected_pose"),
        "prompt": data.get("prompt")
    })