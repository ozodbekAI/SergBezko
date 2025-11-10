from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from database import async_session_maker
from database.repositories import (UserRepository, TaskRepository, PaymentRepository, BotMessageRepository, 
                                   PoseElementRepository, SceneElementRepository,
                                   AdminLogRepository)
from states import AdminMessageStates, AdminPoseStates, AdminSceneStates
from admin_keyboards import (get_admin_main_menu, get_message_selection_keyboard,
                             get_media_type_keyboard, get_pose_management_keyboard,
                             get_scene_management_keyboard, get_pose_groups_keyboard,
                             get_scene_groups_keyboard, get_element_type_keyboard,
                             get_admin_back_keyboard)
from keyboards import get_main_menu
import logging
import re

logger = logging.getLogger(__name__)
router = Router(name="admin")


# Safe edit helper
async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    if callback.message.text is None:
        try:
            await callback.message.delete()
            logger.info(f"Deleted non-text message {callback.message.message_id}")
        except Exception as e:
            logger.warning(f"Delete failed: {e}")
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Edit failed: {e}. Falling back to answer.")
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def check_admin(callback: CallbackQuery) -> bool:
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        is_admin = await user_repo.is_admin(callback.from_user.id)
    return is_admin

async def check_admin_message(message: Message) -> bool:
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        is_admin = await user_repo.is_admin(message.from_user.id)
    return is_admin


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not await check_admin_message(message):
        await message.answer("❌ У вас нет доступа к админ панели.")
        return
    
    await state.clear()
    await message.answer(
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin back callback data: {callback.data}, user: {callback.from_user.id}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    await safe_edit_text(
        callback,
        "🔧 <b>Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin stats callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        payment_repo = PaymentRepository(session)
        
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        total_balance = await user_repo.get_total_balance()
        total_tasks = await task_repo.get_total_tasks()
        completed_tasks = await task_repo.get_completed_tasks()
        total_payments = await payment_repo.get_total_payments()
        total_credits = await payment_repo.get_total_credits_sold()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных (30 дней): <b>{active_users}</b>\n"
        f"💰 Общий баланс: <b>{total_balance}</b> кредитов\n\n"
        f"📋 Всего задач: <b>{total_tasks}</b>\n"
        f"✅ Завершенных: <b>{completed_tasks}</b>\n\n"
        f"💳 Успешных платежей: <b>{total_payments}</b>\n"
        f"🎁 Продано кредитов: <b>{total_credits}</b>"
    )
    
    await safe_edit_text(
        callback,
        stats_text,
        reply_markup=get_admin_back_keyboard()
    )



@router.callback_query(F.data == "admin_messages")
async def admin_messages_menu(callback: CallbackQuery, state: FSMContext):
    """Xabarlarni boshqarish menyusi"""
    logger.info(f"Admin messages callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    await safe_edit_text(
        callback,
        "📝 <b>Управление сообщениями бота</b>\n\n"
        "Выберите сообщение для редактирования:",
        reply_markup=get_message_selection_keyboard()
    )


@router.callback_query(F.data.startswith("edit_msg_"))
async def select_message_to_edit(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Edit msg callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    message_key = callback.data.replace("edit_msg_", "")

    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        bot_msg = await msg_repo.get_message(message_key)
    
    current_text = bot_msg.text if bot_msg else "Не установлено"
    media_info = ""
    if bot_msg and bot_msg.media_type:
        media_info = f"\n📎 Медиа: {bot_msg.media_type}"
    
    await state.set_state(AdminMessageStates.entering_text)
    await state.update_data(message_key=message_key)
    
    await safe_edit_text(
        callback,
        f"✏️ <b>Редактирование сообщения</b>\n\n"
        f"Текущий текст:\n{current_text}{media_info}\n\n"
        f"Введите новый текст сообщения:",
        reply_markup=get_admin_back_keyboard()
    )


@router.message(AdminMessageStates.entering_text, F.text)
async def message_text_received(message: Message, state: FSMContext):
    """Xabar matni qabul qilish"""
    data = await state.get_data()
    
    await state.update_data(new_text=message.text)
    await state.set_state(AdminMessageStates.uploading_media)
    
    await message.answer(
        "✅ Текст получен!\n\n"
        "Теперь выберите тип медиа (или пропустите):",
        reply_markup=get_media_type_keyboard()
    )


@router.callback_query(AdminMessageStates.uploading_media, F.data.startswith("media_"))
async def media_type_selected(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Media type callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    media_type = callback.data.replace("media_", "")
    
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data["new_text"]
    
    if media_type == "none":
        async with async_session_maker() as session:
            msg_repo = BotMessageRepository(session)
            await msg_repo.set_message(message_key, new_text, None, None)
            
            log_repo = AdminLogRepository(session)
            await log_repo.log_action(
                callback.from_user.id,
                "update_message",
                f"Updated message: {message_key}"
            )
        
        await safe_edit_text(
            callback,
            "✅ Сообщение успешно обновлено!",
            reply_markup=get_admin_main_menu()
        )
        await state.clear()
    else:
        # Media yuklashni kutish
        await state.update_data(media_type=media_type)
        await safe_edit_text(
            callback,
            f"📤 Теперь отправьте {media_type} (фото или видео):",
            reply_markup=get_admin_back_keyboard()
        )


@router.message(AdminMessageStates.uploading_media, F.photo | F.video)
async def media_received(message: Message, state: FSMContext):
    """Media qabul qilish"""
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data["new_text"]

    if message.photo:
        file_id = message.photo[-1].file_id
        actual_media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        actual_media_type = "video"
    else:
        await message.answer("❌ Неверный формат. Отправьте фото или видео.")
        return
    
    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        await msg_repo.set_message(message_key, new_text, actual_media_type, file_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "update_message_with_media",
            f"Updated message: {message_key} with {actual_media_type}"
        )
    
    await message.answer(
        "✅ Сообщение с медиа успешно обновлено!",
        reply_markup=get_admin_main_menu()
    )
    await state.clear()


@router.callback_query(F.data == "admin_poses")
async def admin_poses_menu(callback: CallbackQuery, state: FSMContext):
    """Pozalarni boshqarish menyusi"""
    logger.info(f"Admin poses callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        all_poses = await pose_repo.get_all_poses()
    
    poses_info = ""
    for pose_id, elements in all_poses.items():
        poses_info += f"\n📌 <b>{pose_id}</b>: {len(elements)} элементов"
    
    await safe_edit_text(
        callback,
        f"🤸 <b>Управление позами</b>\n"
        f"{poses_info if poses_info else 'Нет поз'}\n\n"
        f"Выберите действие:",
        reply_markup=get_pose_management_keyboard()
    )


@router.callback_query(F.data == "pose_add")
async def pose_add_start(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Pose add callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.set_state(AdminPoseStates.selecting_group)
    
    await safe_edit_text(
        callback,
        "➕ <b>Добавление позы</b>\n\n"
        "Выберите группу позы:",
        reply_markup=get_pose_groups_keyboard()
    )


@router.callback_query(AdminPoseStates.selecting_group, F.data.startswith("pose_group_"))
async def pose_group_selected(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Pose group callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    group = callback.data.replace("pose_group_", "")
    await state.update_data(pose_group=group)
    
    await safe_edit_text(
        callback,
        f"Группа: <b>{group}</b>\n\n"
        f"Теперь введите ID позы (например: standing_straight):",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminPoseStates.entering_pose_id)


@router.message(AdminPoseStates.entering_pose_id, F.text)
async def pose_id_received(message: Message, state: FSMContext):
    logger.info(f"Pose ID received: {message.text}")
    pose_id = message.text.strip()
    await state.update_data(pose_id=pose_id)
    
    await message.answer(
        f"ID: <code>{pose_id}</code>\n\n"
        f"Выберите тип элемента:",
        parse_mode="HTML",
        reply_markup=get_element_type_keyboard()
    )
    await state.set_state(AdminPoseStates.selecting_element_type)


@router.callback_query(AdminPoseStates.selecting_element_type, F.data.startswith("elem_type_"))
async def element_type_selected(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Element type callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    elem_type = callback.data.replace("elem_type_", "")
    await state.update_data(element_type=elem_type)
    
    await safe_edit_text(
        callback,
        f"Тип: <b>{elem_type}</b>\n\n"
        f"Введите название элемента (на русском):",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminPoseStates.entering_element_name)


@router.message(AdminPoseStates.entering_element_name, F.text)
async def element_name_received(message: Message, state: FSMContext):
    logger.info(f"Element name received: {message.text}")
    element_name = message.text.strip()
    await state.update_data(element_name=element_name)
    
    await message.answer(
        f"Название: <b>{element_name}</b>\n\n"
        f"Введите prompt (на английском):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminPoseStates.entering_element_prompt)


@router.message(AdminPoseStates.entering_element_prompt, F.text)
async def element_prompt_received(message: Message, state: FSMContext):
    logger.info(f"Element prompt received: {message.text[:50]}...")
    element_prompt = message.text.strip()
    data = await state.get_data()

    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        await pose_repo.add_element(
            pose_id=data["pose_id"],
            element_type=data["element_type"],
            name=data["element_name"],
            prompt=element_prompt,
            group=data["pose_group"]
        )
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_pose_element",
            f"Added element to {data['pose_id']}: {data['element_name']}"
        )
    
    await message.answer(
        "✅ Элемент позы успешно добавлен!\n\n"
        f"ID позы: <code>{data['pose_id']}</code>\n"
        f"Название: {data['element_name']}\n"
        f"Prompt: <code>{element_prompt}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_main_menu()
    )
    await state.clear()


@router.callback_query(F.data == "pose_list")
async def pose_list_handler(callback: CallbackQuery, state: FSMContext):
    """Barcha pose elementlarini ko'rsatish"""
    logger.info(f"Pose list callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        pose_repo = PoseElementRepository(session)
        all_poses = await pose_repo.get_all_poses()
    
    if not all_poses:
        await safe_edit_text(
            callback,
            "❌ Нет элементов поз",
            reply_markup=get_admin_main_menu()
        )
        return
    
    text = "📋 <b>Список элементов поз:</b>\n\n"
    for pose_id, elements in all_poses.items():
        text += f"<b>{pose_id}</b> ({len(elements)} элементов):\n"
        for elem in elements:
            text += f"  • {elem.name} ({elem.element_type})\n"
            text += f"    <code>{elem.prompt}</code>\n"
        text += "\n"
    
    await safe_edit_text(
        callback,
        text,
        reply_markup=get_admin_back_keyboard()
    )


@router.callback_query(F.data == "admin_scenes")
async def admin_scenes_menu(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin scenes callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        all_scenes = await scene_repo.get_all_scenes()
    
    scenes_info = ""
    for scene_id, elements in all_scenes.items():
        scenes_info += f"\n📌 <b>{scene_id}</b>: {len(elements)} элементов"
    
    await safe_edit_text(
        callback,
        f"🌆 <b>Управление сценами</b>\n"
        f"{scenes_info if scenes_info else 'Нет сцен'}\n\n"
        f"Выберите действие:",
        reply_markup=get_scene_management_keyboard()
    )


@router.callback_query(F.data == "scene_add")
async def scene_add_start(callback: CallbackQuery, state: FSMContext):
    """Scene qo'shish boshlash"""
    logger.info(f"Scene add callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.set_state(AdminSceneStates.selecting_group)
    
    await safe_edit_text(
        callback,
        "➕ <b>Добавление сцены</b>\n\n"
        "Выберите группу сцены:",
        reply_markup=get_scene_groups_keyboard()
    )


@router.callback_query(AdminSceneStates.selecting_group, F.data.startswith("scene_group_"))
async def scene_group_selected(callback: CallbackQuery, state: FSMContext):
    """Scene guruhi tanlangan"""
    logger.info(f"Scene group callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    group = callback.data.replace("scene_group_", "")
    await state.update_data(scene_group=group)
    
    await safe_edit_text(
        callback,
        f"Группа: <b>{group}</b>\n\n"
        f"Теперь введите ID сцены (например: boutique_showroom):",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_scene_id)


@router.message(AdminSceneStates.entering_scene_id, F.text)
async def scene_id_received(message: Message, state: FSMContext):
    logger.info(f"Scene ID received: {message.text}")
    scene_id = message.text.strip()
    await state.update_data(scene_id=scene_id)
    
    await message.answer(
        f"ID: <code>{scene_id}</code>\n\n"
        f"Выберите тип элемента:",
        parse_mode="HTML",
        reply_markup=get_element_type_keyboard()
    )
    await state.set_state(AdminSceneStates.selecting_element_type)


@router.callback_query(AdminSceneStates.selecting_element_type, F.data.startswith("elem_type_"))
async def scene_element_type_selected(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Scene element type callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    elem_type = callback.data.replace("elem_type_", "")
    await state.update_data(element_type=elem_type)
    
    await safe_edit_text(
        callback,
        f"Тип: <b>{elem_type}</b>\n\n"
        f"Введите название элемента (на русском):",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_element_name)


@router.message(AdminSceneStates.entering_element_name, F.text)
async def scene_element_name_received(message: Message, state: FSMContext):
    logger.info(f"Scene element name received: {message.text}")
    element_name = message.text.strip()
    await state.update_data(element_name=element_name)
    
    await message.answer(
        f"Название: <b>{element_name}</b>\n\n"
        f"Введите prompt для Дальний план (far, на английском):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_far)


@router.message(AdminSceneStates.entering_prompt_far, F.text)
async def scene_prompt_far_received(message: Message, state: FSMContext):
    prompt_far = message.text.strip()
    await state.update_data(prompt_far=prompt_far)
    
    await message.answer(
        f"Far: <code>{prompt_far[:50]}...</code>\n\n"
        f"Введите prompt для Средний план (medium):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_medium)


@router.message(AdminSceneStates.entering_prompt_medium, F.text)
async def scene_prompt_medium_received(message: Message, state: FSMContext):
    """Medium prompt qabul qilish"""
    prompt_medium = message.text.strip()
    await state.update_data(prompt_medium=prompt_medium)
    
    await message.answer(
        f"Medium: <code>{prompt_medium[:50]}...</code>\n\n"
        f"Введите prompt для Крупный план (close):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_close)


@router.message(AdminSceneStates.entering_prompt_close, F.text)
async def scene_prompt_close_received(message: Message, state: FSMContext):
    prompt_close = message.text.strip()
    await state.update_data(prompt_close=prompt_close)
    
    await message.answer(
        f"Close: <code>{prompt_close[:50]}...</code>\n\n"
        f"Введите prompt для Боковой вид (side):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_side)


@router.message(AdminSceneStates.entering_prompt_side, F.text)
async def scene_prompt_side_received(message: Message, state: FSMContext):
    prompt_side = message.text.strip()
    await state.update_data(prompt_side=prompt_side)
    
    await message.answer(
        f"Side: <code>{prompt_side[:50]}...</code>\n\n"
        f"Введите prompt для Вид со спины (back):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_back)


@router.message(AdminSceneStates.entering_prompt_back, F.text)
async def scene_prompt_back_received(message: Message, state: FSMContext):
    prompt_back = message.text.strip()
    await state.update_data(prompt_back=prompt_back)
    
    await message.answer(
        f"Back: <code>{prompt_back[:50]}...</code>\n\n"
        f"Введите prompt для Динамический кадр (motion):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await state.set_state(AdminSceneStates.entering_prompt_motion)


@router.message(AdminSceneStates.entering_prompt_motion, F.text)
async def scene_prompt_motion_received(message: Message, state: FSMContext):
    logger.info(f"Scene prompts received, saving...")
    prompt_motion = message.text.strip()
    data = await state.get_data()

    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        await scene_repo.add_element(
            scene_id=data["scene_id"],
            element_type=data["element_type"],
            name=data["element_name"],
            prompt_far=data["prompt_far"],
            prompt_medium=data["prompt_medium"],
            prompt_close=data["prompt_close"],
            prompt_side=data.get("prompt_side", ""),
            prompt_back=data.get("prompt_back", ""),
            prompt_motion=prompt_motion,
            group=data["scene_group"]
        )
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_scene_element",
            f"Added element to {data['scene_id']}: {data['element_name']}"
        )
    
    await message.answer(
        "✅ Элемент сцены успешно добавлен!\n\n"
        f"ID сцены: <code>{data['scene_id']}</code>\n"
        f"Название: {data['element_name']}\n"
        f"Prompts сохранены для всех планов.",
        parse_mode="HTML",
        reply_markup=get_admin_main_menu()
    )
    await state.clear()


@router.callback_query(F.data == "scene_list")
async def scene_list_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Scene list callback: {callback.data}")
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        scene_repo = SceneElementRepository(session)
        all_scenes = await scene_repo.get_all_scenes()
    
    if not all_scenes:
        await safe_edit_text(
            callback,
            "❌ Нет элементов сцен",
            reply_markup=get_admin_main_menu()
        )
        return
    
    text = "📋 <b>Список элементов сцен:</b>\n\n"
    for scene_id, elements in all_scenes.items():
        text += f"<b>{scene_id}</b> ({len(elements)} элементов):\n"
        for elem in elements:
            text += f"  • {elem.name} ({elem.element_type})\n"
            text += f"    Far: <code>{elem.prompt_far[:30] if elem.prompt_far else 'N/A'}...</code>\n"
            text += f"    Medium: <code>{elem.prompt_medium[:30] if elem.prompt_medium else 'N/A'}...</code>\n"
            text += f"    Close: <code>{elem.prompt_close[:30] if elem.prompt_close else 'N/A'}...</code>\n"
            text += f"    Side/Back/Motion: ... (saved)\n"
        text += "\n"
    
    await safe_edit_text(
        callback,
        text,
        reply_markup=get_admin_back_keyboard()
    )



@router.message(Command("add_credits"))
async def add_credits_command(message: Message):
    if not await check_admin_message(message):
        await message.answer("❌ Нет доступа.")
        return
    
    text = message.text.strip()
    match = re.match(r'/add_credits\s+@?(\w+)\s+(\d+)', text)
    if not match:
        await message.answer("❌ Формат: /add_credits @username N")
        return
    
    username = match.group(1)
    amount = int(match.group(2))
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_username(username)
        if not user:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        
        await user_repo.update_balance(user.telegram_id, amount)
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_credits",
            f"Added {amount} credits to @{username} (ID: {user.telegram_id})"
        )
    
    await message.answer(f"✅ Добавлено {amount} кредитов пользователю @{username} (баланс: {user.balance})")


@router.message(Command("balance"))
async def balance_command(message: Message):
    """ /balance @user - Show user balance """
    if not await check_admin_message(message):
        await message.answer("❌ Нет доступа.")
        return
    
    text = message.text.strip()
    match = re.match(r'/balance\s+@?(\w+)', text)
    if not match:
        await message.answer("❌ Формат: /balance @username")
        return
    
    username = match.group(1)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_username(username)
        if not user:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
    
    await message.answer(f"💰 Баланс @{username}: <b>{user.balance}</b> кредитов", parse_mode="HTML")


@router.message(Command("stats"))
async def stats_command(message: Message):
    """ /stats - Global statistics """
    if not await check_admin_message(message):
        await message.answer("❌ Нет доступа.")
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        payment_repo = PaymentRepository(session)
        
        total_users = await user_repo.get_total_users()
        active_users = await user_repo.get_total_active_users()
        total_balance = await user_repo.get_total_balance()
        total_tasks = await task_repo.get_total_tasks()
        completed_tasks = await task_repo.get_completed_tasks()
        total_payments = await payment_repo.get_total_payments()
        total_credits = await payment_repo.get_total_credits_sold()
    
    stats_text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"🟢 Активных: <b>{active_users}</b>\n"
        f"💰 Общий баланс: <b>{total_balance}</b>\n"
        f"📋 Задач: <b>{total_tasks}</b> (завершено: <b>{completed_tasks}</b>)\n"
        f"💳 Платежей: <b>{total_payments}</b>\n"
        f"🎁 Кредитов продано: <b>{total_credits}</b>"
    )
    
    await message.answer(stats_text, parse_mode="HTML")


@router.message(Command("ban"))
async def ban_command(message: Message):
    if not await check_admin_message(message):
        await message.answer("❌ Нет доступа.")
        return
    
    text = message.text.strip()
    match = re.match(r'/ban\s+@?(\w+)', text)
    if not match:
        await message.answer("❌ Формат: /ban @username")
        return
    
    username = match.group(1)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_username(username)
        if not user:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        
        if user.is_banned:
            await message.answer(f"❌ Пользователь @{username} уже заблокирован.")
            return
        
        await user_repo.ban_user(user.telegram_id)
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "ban_user",
            f"Banned @{username} (ID: {user.telegram_id})"
        )
    
    await message.answer(f"🚫 Пользователь @{username} заблокирован.")


@router.message(Command("unban"))
async def unban_command(message: Message):
    if not await check_admin_message(message):
        await message.answer("❌ Нет доступа.")
        return
    
    text = message.text.strip()
    match = re.match(r'/unban\s+@?(\w+)', text)
    if not match:
        await message.answer("❌ Формат: /unban @username")
        return
    
    username = match.group(1)
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_username(username)
        if not user:
            await message.answer(f"❌ Пользователь @{username} не найден.")
            return
        
        if not user.is_banned:
            await message.answer(f"❌ Пользователь @{username} не заблокирован.")
            return
        
        await user_repo.unban_user(user.telegram_id)
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "unban_user",
            f"Unbanned @{username} (ID: {user.telegram_id})"
        )
    
    await message.answer(f"✅ Пользователь @{username} разблокирован.")


@router.callback_query(F.data.startswith("admin_") | F.data.startswith("pose_") | F.data.startswith("scene_") | F.data.startswith("elem_type_"))
async def debug_unhandled_admin(callback: CallbackQuery, state: FSMContext):
    """Not handled callback'lar uchun log (faqat admin uchun)."""
    logger.warning(f"Unhandled admin callback: data='{callback.data}', state='{await state.get_state()}', user={callback.from_user.id}")
    await callback.answer("❌ Неизвестное действие. Вернитесь в меню.", show_alert=True)