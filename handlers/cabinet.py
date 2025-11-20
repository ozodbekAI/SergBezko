from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import UserRepository, PaymentRepository
from keyboards import get_payment_packages, get_cabinet_menu
from services.config_loader import config_loader
from services.payment_services import payment_service
import asyncio
import logging

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "cabinet_balance")
async def show_balance(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    
    # Database'dan paketlarni olish (async)
    packages = await config_loader.get_payment_packages()
    
    text = (
        f"💰 Ваш текущий баланс: {user.balance} кредитов\n\n"
        "Выберите пакет для пополнения:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_payment_packages(packages))


@router.callback_query(F.data.startswith("buy_"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.message.edit_text(
            "❌ Неверный формат пакета. Попробуйте снова.", 
            reply_markup=get_cabinet_menu()
        )
        return
    
    credits = int(parts[1])
    price = float(parts[2])
    
    loading_msg = await callback.message.edit_text(
        "⏳ Создаём платёж...\n\nПодождите несколько секунд.",
        reply_markup=None
    )
    
    async with async_session_maker() as session:
        try:
            confirmation_url, payment_id = await payment_service.create_payment(
                session=session,
                telegram_id=callback.from_user.id,
                credits=credits,
                amount=price
            )

            payment_msg = await loading_msg.edit_text(
                f"💳 <b>Пополнение баланса</b>\n\n"
                f"📦 Пакет: {credits} кредитов\n"
                f"💰 Сумма: {price} ₽\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты кредиты автоматически зачислятся на ваш баланс.\n\n"
                f"⏱ Ссылка действительна 10 минут.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
                    [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
                ])
            )
            
            asyncio.create_task(check_payment_status(
                payment_id=payment_id,
                telegram_id=callback.from_user.id,
                bot=callback.message.bot,
                message_id=payment_msg.message_id,
                chat_id=callback.message.chat.id,
                credits=credits
            ))
            
        except Exception as e:
            logger.error(f"Payment creation error: {e}", exc_info=True)
            await loading_msg.edit_text(
                f"❌ <b>Ошибка при создании платежа</b>\n\n"
                f"Не удалось создать платёж. Попробуйте позже или обратитесь в поддержку.\n\n"
                f"<i>Детали: {str(e)[:100]}</i>",
                parse_mode="HTML",
                reply_markup=get_cabinet_menu()
            )


async def check_payment_status(payment_id: str, telegram_id: int, bot, message_id: int, chat_id: int, credits: int):
    max_attempts = 60
    
    for attempt in range(max_attempts):
        await asyncio.sleep(10)
        
        async with async_session_maker() as session:
            try:
                status_data = await payment_service.check_payment_status(payment_id, session)
                status = status_data["status"]
                paid = status_data["paid"]
                
                if paid:
                    credits_amount = int(status_data["metadata"].get("credits", credits))
                    
                    async with async_session_maker() as update_session:
                        user_repo = UserRepository(update_session)
                        user = await user_repo.get_user_by_telegram_id(telegram_id)
                        if user:
                            user = await user_repo.update_balance(telegram_id, credits_amount)
                        else:
                            logger.error(f"User with telegram_id {telegram_id} not found")
                            return
                    
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except:
                        pass
                    
                    await bot.send_message(
                        telegram_id,
                        f"✅ <b>Платёж успешно завершён!</b>\n\n"
                        f"💰 Зачислено: {credits_amount} кредитов\n"
                        f"📊 Ваш баланс: {user.balance} кредитов\n\n"
                        f"Спасибо за покупку! 🎉",
                        parse_mode="HTML",
                        reply_markup=get_cabinet_menu()
                    )
                    return
                
                elif status in ["cancelled", "rejected"]:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except:
                        pass
                    
                    await bot.send_message(
                        telegram_id,
                        "❌ <b>Платёж отменён</b>\n\n"
                        "Платёж был отменён или отклонён.\n"
                        "Попробуйте выбрать другой пакет.",
                        parse_mode="HTML",
                        reply_markup=get_cabinet_menu()
                    )
                    return
                
            except Exception as e:
                logger.error(f"Error checking payment status (attempt {attempt + 1}): {e}", exc_info=True)
    
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass
    
    await bot.send_message(
        telegram_id,
        "⏱ <b>Время ожидания истекло</b>\n\n"
        "Платёж не был завершён в течение 10 минут.\n"
        "Если вы оплатили заказ, кредиты будут зачислены автоматически.\n\n"
        "Для создания нового платежа перейдите в раздел пополнения.",
        parse_mode="HTML",
        reply_markup=get_cabinet_menu()
    )


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery):
    await callback.answer("Платёж отменён", show_alert=True)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer(
        "❌ Платёж отменён\n\n"
        "Вы можете создать новый платёж в любое время.",
        reply_markup=get_cabinet_menu()
    )


@router.callback_query(F.data == "cabinet_faq")
async def show_faq(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    pricing = config_loader.pricing
    
    faq_text = """
📋 <b>Справка по использованию бота</b>

<b>📸 Как отправлять фото:</b>
• Готовая карточка товара: 1 фото
• Нормализация (своя модель): 2 фото
• Нормализация (новая модель): 1 фото
• Видео: 1 фото
• Фото (смена сцены/позы): 1 фото

<b>💡 Важно знать:</b>
• Подписи к фото игнорируются во всех режимах, кроме "Свой промпт"
• В режиме "Свой промпт" текст автоматически переводится на английский
• Не отправляйте альбомы - только отдельные фото
• После результата можно нажать "Повторить" для новой генерации

<b>💰 Стоимость:</b>
• Готовая карточка товара: {pc_cost} кредит за результат
• Нормализация: {norm_cost} кредита
• Видео Баланс: {video_balance} кредитов
• Видео Про 6 сек: {video_pro6} кредитов
• Видео Про 10 сек: {video_pro10} кредитов
• Видео Супер Про: {video_super} кредитов
• Фото (смена сцены/позы): {photo_cost} кредит за результат
• Фото (свой сценарий): {photo_custom} кредит

<b>⏱ Время ожидания:</b>
• Фото: 10-30 секунд
• Видео: 2-5 минут

<b>❗ При ошибках:</b>
• Кредиты автоматически возвращаются на баланс
• Если проблема повторяется, попробуйте другое фото

<b>💳 Пополнение баланса:</b>
• Доступны пакеты из базы данных
• Оплата через ЮKassa (безопасно)
• Зачисление автоматическое после оплаты
    """.format(
        pc_cost=pricing["product_card"]["per_result"],
        norm_cost=pricing["normalize"]["own_model"],
        video_balance=pricing["video"]["balance"]["cost"],
        video_pro6=pricing["video"]["pro_6"]["cost"],
        video_pro10=pricing["video"]["pro_10"]["cost"],
        video_super=pricing["video"]["super_6"]["cost"],
        photo_cost=pricing["photo"]["scene_change"],
        photo_custom=pricing["photo"]["custom_scenario"]
    )
    
    await callback.message.edit_text(faq_text, parse_mode="HTML", reply_markup=get_cabinet_menu())


@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "👤 Мой кабинет\n\nВыберите действие:",
        reply_markup=get_cabinet_menu()
    )