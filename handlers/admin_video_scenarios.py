import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database import async_session_maker
from database.repositories import VideoScenarioRepository
from states import AdminVideoScenarioStates

from admin_keyboards import (
    get_admin_video_main_menu,
    get_video_scenarios_list,
    get_video_scenario_detail_keyboard,
    get_video_scenario_edit_menu,
    get_confirm_delete_keyboard_video,
)

logger = logging.getLogger(__name__)
router = Router(name="admin_video_scenarios")


def _truncate(text: str, limit: int = 180) -> str:
    if text is None:
        return ""
    return text if len(text) <= limit else text[:limit - 1] + "…"

@router.callback_query(F.data == "admin_video_scenarios")
async def admin_video_entry(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await cb.message.edit_text("🎬 Сценарии видео — админ меню", reply_markup=get_admin_video_main_menu())
    await state.set_state(AdminVideoScenarioStates.main)

@router.callback_query(F.data == "vidsc_view")
async def vids_view_list(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        scenarios = await repo.get_all()
    if not scenarios:
        await cb.message.edit_text("Пока нет сценариев. Нажмите «➕ Добавить сценарий».", reply_markup=get_admin_video_main_menu())
        return
    await cb.message.edit_text("👁 Сценарии (активные сверху):", reply_markup=get_video_scenarios_list(scenarios, action="view"))

@router.callback_query(F.data.startswith("vidsc_view_"))
async def vids_view_detail(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_view_"))
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.get_by_id(sid)
    if not s:
        await cb.message.edit_text("❌ Сценарий не найден.", reply_markup=get_admin_video_main_menu())
        return
    status = "✅ Активен" if s.is_active else "🚫 Выключен"
    text = (
        f"🎬 <b>{s.name}</b>\n"
        f"ID: <code>{s.id}</code>\n"
        f"Порядок: <b>{s.order_index}</b>\n"
        f"Статус: {status}\n\n"
        f"📝 Промпт:\n<code>{_truncate(s.prompt, 200)}</code>"
    )
    await cb.message.edit_text(text, reply_markup=get_video_scenario_detail_keyboard(s.id, s.is_active), parse_mode="HTML")

@router.callback_query(F.data == "vidsc_add")
async def vids_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AdminVideoScenarioStates.entering_name)
    await cb.message.edit_text("➕ Введите <b>название</b> сценария:", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.entering_name, F.text)
async def vids_add_name(msg: Message, state: FSMContext):
    await state.update_data(new_name=msg.text.strip())
    await state.set_state(AdminVideoScenarioStates.entering_prompt)
    await msg.answer("📝 Введите <b>промпт</b> сценария:", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.entering_prompt, F.text)
async def vids_add_prompt(msg: Message, state: FSMContext):
    await state.update_data(new_prompt=msg.text.strip())
    await state.set_state(AdminVideoScenarioStates.entering_order)
    await msg.answer("🔢 Введите <b>порядок</b> (целое число, по умолчанию 0):", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.entering_order, F.text)
async def vids_add_order(msg: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("new_name")
    prompt = data.get("new_prompt")
    try:
        order_index = int(msg.text.strip())
    except Exception:
        order_index = 0

    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        try:
            obj = await repo.add(name=name, prompt=prompt, order_index=order_index, is_active=True)
        except Exception as e:
            logger.exception("Create scenario failed")
            await msg.answer(f"❌ Не удалось создать сценарий: {e}")
            await state.clear()
            return

    await state.clear()
    await msg.answer(f"✅ Сценарий «<b>{name}</b>» добавлен (#{order_index}).", parse_mode="HTML")
    # Show list
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        scenarios = await repo.get_all()
    await msg.answer("👁 Сценарии:", reply_markup=get_video_scenarios_list(scenarios, action="view"))

@router.callback_query(F.data == "vidsc_edit_menu")
async def vids_edit_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        scenarios = await repo.get_all()
    if not scenarios:
        await cb.message.edit_text("Сценариев пока нет.", reply_markup=get_admin_video_main_menu())
        return
    await state.set_state(AdminVideoScenarioStates.selecting_scenario)
    await cb.message.edit_text("✏️ Выберите сценарий для редактирования:", reply_markup=get_video_scenarios_list(scenarios, action="edit"))

@router.callback_query(AdminVideoScenarioStates.selecting_scenario, F.data.startswith("vidsc_edit_"))
async def vids_edit_pick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_edit_"))
    await state.update_data(edit_id=sid)
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.get_by_id(sid)
    if not s:
        await cb.message.edit_text("❌ Сценарий не найден.", reply_markup=get_admin_video_main_menu())
        await state.clear()
        return
    await state.set_state(AdminVideoScenarioStates.editing_menu)
    await cb.message.edit_text(
        f"✏️ Редактирование «{s.name}»: выберите поле:",
        reply_markup=get_video_scenario_edit_menu(sid)
    )

@router.callback_query(AdminVideoScenarioStates.editing_menu, F.data.startswith("vidsc_edit_name_"))
async def vids_edit_name_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_edit_name_"))
    await state.update_data(edit_id=sid)
    await state.set_state(AdminVideoScenarioStates.editing_name)
    await cb.message.edit_text("✏️ Введите новое <b>название</b>:", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.editing_name, F.text)
async def vids_edit_name_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("edit_id")
    new_name = msg.text.strip()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.update(sid, name=new_name)
    await state.set_state(AdminVideoScenarioStates.editing_menu)
    await msg.answer(f"✅ Имя обновлено: <b>{s.name}</b>", parse_mode="HTML", reply_markup=get_video_scenario_edit_menu(sid))

@router.callback_query(AdminVideoScenarioStates.editing_menu, F.data.startswith("vidsc_edit_prompt_"))
async def vids_edit_prompt_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_edit_prompt_"))
    await state.update_data(edit_id=sid)
    await state.set_state(AdminVideoScenarioStates.editing_prompt)
    await cb.message.edit_text("📝 Введите новый <b>промпт</b>:", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.editing_prompt, F.text)
async def vids_edit_prompt_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("edit_id")
    new_prompt = msg.text.strip()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.update(sid, prompt=new_prompt)
    await state.set_state(AdminVideoScenarioStates.editing_menu)
    await msg.answer("✅ Промпт обновлен.", reply_markup=get_video_scenario_edit_menu(sid))

@router.callback_query(AdminVideoScenarioStates.editing_menu, F.data.startswith("vidsc_edit_order_"))
async def vids_edit_order_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_edit_order_"))
    await state.update_data(edit_id=sid)
    await state.set_state(AdminVideoScenarioStates.editing_order)
    await cb.message.edit_text("🔢 Введите новое <b>значение порядка</b> (целое число):", parse_mode="HTML")

@router.message(AdminVideoScenarioStates.editing_order, F.text)
async def vids_edit_order_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("edit_id")
    try:
        new_order = int(msg.text.strip())
    except Exception:
        await msg.answer("❌ Нужно целое число. Повторите ввод.")
        return
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.update(sid, order_index=new_order)
    await state.set_state(AdminVideoScenarioStates.editing_menu)
    await msg.answer(f"✅ Порядок обновлен: <b>{s.order_index}</b>", parse_mode="HTML", reply_markup=get_video_scenario_edit_menu(sid))

@router.callback_query(F.data == "vidsc_toggle_menu")
async def vids_toggle_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        scenarios = await repo.get_all()
    if not scenarios:
        await cb.message.edit_text("Сценариев пока нет.", reply_markup=get_admin_video_main_menu())
        return
    await cb.message.edit_text("🔄 Выберите сценарий для включения/выключения:", reply_markup=get_video_scenarios_list(scenarios, action="toggle"))

@router.callback_query(F.data.startswith("vidsc_toggle_"))
async def vids_toggle(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_toggle_"))
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.get_by_id(sid)
        if not s:
            await cb.message.edit_text("❌ Сценарий не найден.", reply_markup=get_admin_video_main_menu())
            return
        s = await repo.update(sid, is_active=not s.is_active)
    status = "включен ✅" if s.is_active else "выключен 🚫"
    await cb.message.edit_text(f"🎬 «{s.name}» теперь {status}.", reply_markup=get_admin_video_main_menu())

@router.callback_query(F.data == "vidsc_delete_menu")
async def vids_delete_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        scenarios = await repo.get_all()
    if not scenarios:
        await cb.message.edit_text("Сценариев пока нет.", reply_markup=get_admin_video_main_menu())
        return
    await cb.message.edit_text("🗑 Выберите сценарий для удаления:", reply_markup=get_video_scenarios_list(scenarios, action="delete"))

@router.callback_query(F.data.startswith("vidsc_delete_"))
async def vids_delete_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_delete_"))
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        s = await repo.get_by_id(sid)
    if not s:
        await cb.message.edit_text("❌ Сценарий не найден.", reply_markup=get_admin_video_main_menu())
        return
    await state.update_data(delete_id=sid)
    await cb.message.edit_text(
        f"⚠️ Удалить «{s.name}»?\nДействие необратимо.",
        reply_markup=get_confirm_delete_keyboard_video(sid)
    )

@router.callback_query(F.data.startswith("vidsc_delete_confirm_"))
async def vids_delete_do(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    sid = int(cb.data.removeprefix("vidsc_delete_confirm_"))
    async with async_session_maker() as session:
        repo = VideoScenarioRepository(session)
        await repo.delete(sid)
        scenarios = await repo.get_all()
    await state.clear()
    await cb.message.edit_text("✅ Удалено.\n\nОставшиеся сценарии:", reply_markup=get_video_scenarios_list(scenarios, action="view"))
