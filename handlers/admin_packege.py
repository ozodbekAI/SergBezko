from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import async_session_maker
from database.repositories import UserRepository, PaymentPackageRepository, AdminLogRepository
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

logger = logging.getLogger(__name__)
router = Router(name="admin_packages")


class AdminPackageStates(StatesGroup):
    entering_label = State()
    entering_credits = State()
    entering_price = State()
    entering_bonus = State()
    editing_label = State()
    editing_credits = State()
    editing_price = State()
    editing_bonus = State()


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


def get_packages_keyboard(packages: list):
    builder = InlineKeyboardBuilder()
    
    for package in packages:
        status = "✅" if package.is_active else "❌"
        bonus_text = f" (+{package.bonus})" if package.bonus else ""
        text = f"{status} {package.label} - {package.price}₽{bonus_text}"
        builder.row(InlineKeyboardButton(
            text=text,
            callback_data=f"pkg_view_{package.id}"
        ))
    
    builder.row(InlineKeyboardButton(text="➕ Добавить пакет", callback_data="pkg_add"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()


def get_package_detail_keyboard(package_id: int, is_active: bool):
    builder = InlineKeyboardBuilder()
    
    status_text = "❌ Отключить" if is_active else "✅ Включить"
    builder.row(InlineKeyboardButton(
        text="✏️ Редактировать",
        callback_data=f"pkg_edit_{package_id}"
    ))
    builder.row(InlineKeyboardButton(
        text=status_text,
        callback_data=f"pkg_toggle_{package_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="🗑 Удалить",
        callback_data=f"pkg_delete_{package_id}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_packages"))
    return builder.as_markup()


def get_cancel_keyboard(back_data: str = "admin_packages"):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=back_data))
    return builder.as_markup()


@router.callback_query(F.data == "admin_packages")
async def show_packages_list(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        packages = await pkg_repo.get_all_packages(only_active=False)
    
    text = "💳 <b>Управление пакетами пополнения</b>\n\n"
    if packages:
        text += f"Всего пакетов: <b>{len(packages)}</b>\n"
        text += f"Активных: <b>{sum(1 for p in packages if p.is_active)}</b>\n\n"
        text += "Выберите пакет для редактирования:"
    else:
        text += "Пакеты не найдены. Добавьте первый пакет."
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_packages_keyboard(packages)
    )


@router.callback_query(F.data.startswith("pkg_view_"))
async def view_package_detail(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    package_id = int(callback.data.replace("pkg_view_", ""))
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        package = await pkg_repo.get_package_by_id(package_id)
    
    if not package:
        await callback.answer("❌ Пакет не найден", show_alert=True)
        return
    
    status = "✅ Активен" if package.is_active else "❌ Отключен"
    bonus_text = f"\n<b>Бонус:</b> {package.bonus}" if package.bonus else ""
    
    text = (
        f"💳 <b>Пакет пополнения #{package.id}</b>\n\n"
        f"<b>Название:</b> {package.label}\n"
        f"<b>Кредиты:</b> {package.credits}\n"
        f"<b>Цена:</b> {package.price} ₽{bonus_text}\n"
        f"<b>Порядок:</b> {package.order_index}\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Создан:</b> {package.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_package_detail_keyboard(package_id, package.is_active)
    )


@router.callback_query(F.data == "pkg_add")
async def add_package_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await state.set_state(AdminPackageStates.entering_label)
    
    await callback.message.edit_text(
        "➕ <b>Добавление нового пакета</b>\n\n"
        "Введите название пакета:\n"
        "<i>Например: 30 кредитов</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(AdminPackageStates.entering_label, F.text)
async def package_label_entered(message: Message, state: FSMContext):
    await state.update_data(label=message.text.strip())
    await state.set_state(AdminPackageStates.entering_credits)
    
    await message.answer(
        "Введите количество кредитов:\n"
        "<i>Например: 30</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(AdminPackageStates.entering_credits, F.text)
async def package_credits_entered(message: Message, state: FSMContext):
    try:
        credits = int(message.text.strip())
        if credits <= 0:
            await message.answer("❌ Количество кредитов должно быть положительным числом")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return
    
    await state.update_data(credits=credits)
    await state.set_state(AdminPackageStates.entering_price)
    
    await message.answer(
        "Введите цену в рублях:\n"
        "<i>Например: 299 или 299.50</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(AdminPackageStates.entering_price, F.text)
async def package_price_entered(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(',', '.'))
        if price <= 0:
            await message.answer("❌ Цена должна быть положительным числом")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return
    
    await state.update_data(price=price)
    await state.set_state(AdminPackageStates.entering_bonus)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ Пропустить", callback_data="pkg_skip_bonus"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_packages"))
    
    await message.answer(
        "Введите текст бонуса (необязательно):\n"
        "<i>Например: +10% бонус</i>\n\n"
        "Или нажмите 'Пропустить'",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "pkg_skip_bonus")
async def skip_bonus(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    await create_package_finalize(callback.message, state, None)


@router.message(AdminPackageStates.entering_bonus, F.text)
async def package_bonus_entered(message: Message, state: FSMContext):
    bonus = message.text.strip() if message.text.strip() else None
    await create_package_finalize(message, state, bonus)


async def create_package_finalize(message: Message, state: FSMContext, bonus: Optional[str]):
    data = await state.get_data()
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        packages = await pkg_repo.get_all_packages(only_active=False)
        next_order = len(packages)
        
        package = await pkg_repo.add_package(
            label=data['label'],
            credits=data['credits'],
            price=data['price'],
            bonus=bonus,
            order_index=next_order
        )
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            message.from_user.id,
            "add_payment_package",
            f"Added package: {package.label} ({package.credits} credits, {package.price}₽)"
        )
    
    await state.clear()
    
    bonus_text = f"\n<b>Бонус:</b> {bonus}" if bonus else ""
    await message.answer(
        f"✅ <b>Пакет успешно создан!</b>\n\n"
        f"<b>Название:</b> {data['label']}\n"
        f"<b>Кредиты:</b> {data['credits']}\n"
        f"<b>Цена:</b> {data['price']} ₽{bonus_text}",
        parse_mode="HTML"
    )
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        packages = await pkg_repo.get_all_packages(only_active=False)
    
    await message.answer(
        "💳 <b>Управление пакетами пополнения</b>\n\n"
        f"Всего пакетов: <b>{len(packages)}</b>\n\n"
        "Выберите пакет для редактирования:",
        parse_mode="HTML",
        reply_markup=get_packages_keyboard(packages)
    )


@router.callback_query(F.data.startswith("pkg_toggle_"))
async def toggle_package(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    package_id = int(callback.data.replace("pkg_toggle_", ""))
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        package = await pkg_repo.toggle_active(package_id)
        
        log_repo = AdminLogRepository(session)
        status = "activated" if package.is_active else "deactivated"
        await log_repo.log_action(
            callback.from_user.id,
            "toggle_payment_package",
            f"{status.capitalize()} package: {package.label}"
        )
    
    status_text = "включен" if package.is_active else "отключен"
    await callback.answer(f"✅ Пакет {status_text}")
    
    await view_package_detail(callback, state)


@router.callback_query(F.data.startswith("pkg_delete_"))
async def delete_package_confirm(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.answer()
    package_id = int(callback.data.replace("pkg_delete_", ""))
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"pkg_delete_confirm_{package_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"pkg_view_{package_id}")
    )
    
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        "Вы уверены, что хотите удалить этот пакет?\n"
        "Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("pkg_delete_confirm_"))
async def delete_package_execute(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        await callback.answer("❌ Нет доступа")
        return
    
    package_id = int(callback.data.replace("pkg_delete_confirm_", ""))
    
    async with async_session_maker() as session:
        pkg_repo = PaymentPackageRepository(session)
        package = await pkg_repo.get_package_by_id(package_id)
        package_label = package.label if package else "Unknown"
        
        await pkg_repo.delete_package(package_id)
        
        log_repo = AdminLogRepository(session)
        await log_repo.log_action(
            callback.from_user.id,
            "delete_payment_package",
            f"Deleted package: {package_label}"
        )
    
    await callback.answer("✅ Пакет удален")
    await show_packages_list(callback, state)